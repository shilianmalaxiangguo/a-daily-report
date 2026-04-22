def render_gem_breathing_step2_section(context):
    context = context or {}
    gem_observation_stocks = context.get("gem_observation_stocks") or []
    filtered_out_gem_candidates = context.get("filtered_out_gem_candidates") or []
    if not gem_observation_stocks and not filtered_out_gem_candidates:
        return []
    display_mvp_mode = bool(context.get("display_mvp_mode"))
    preview = gem_observation_stocks[:2] if display_mvp_mode else gem_observation_stocks[:4]
    lines = [
        "> **主线侧翼弹性层**：若主板强锚仍在，创业板20cm只作为主线白银弹性观察，不单列成独立战场。",
        "> **观察纪律**：只先进观察池，先看均线粘合/蛇形走位能否继续走成右侧确认；确认前只观察不执行。",
    ]
    if filtered_out_gem_candidates:
        filtered_preview = filtered_out_gem_candidates[:2] if display_mvp_mode else filtered_out_gem_candidates[:4]
        filtered_text = "；".join(
            f"{item.get('name', '-')}({item.get('code', '-')})/{item.get('sector', '-')}：{item.get('filtered_reason', '-') or '-'}"
            for item in filtered_preview
        )
        lines.append(f"> **主线过滤提示**：当前有20cm预启动样本，但因非主线被过滤：{filtered_text}")
    if not preview:
        lines.append("")
        return lines
    lines.extend(
        [
            "| 序号 | 股票 | 代码 | 板块 | 预启动层级 | 当前线索 | 预判强度 | 明日原则 |",
            "|------|------|------|------|------------|----------|----------|----------|",
        ]
    )
    for i, item in enumerate(preview, 1):
        lines.append(
            f"| {i} | {item.get('name', '-')} | {item.get('code', '-')} | {item.get('sector', '-')} | "
            f"{item.get('tier', '-') or '-'} | {item.get('abnormal_summary', item.get('note', '-')) or '-'} | "
            f"{item.get('tomorrow_strength', 0)}分 | 先看右侧确认和60分钟确认，不满足继续观察 |"
        )
    lines.append("")
    return lines


def render_gem_breathing_pool_section(context):
    context = context or {}
    gem_observation_stocks = context.get("gem_observation_stocks") or []
    filtered_out_gem_candidates = context.get("filtered_out_gem_candidates") or []
    if not gem_observation_stocks and not filtered_out_gem_candidates:
        return []
    lines = [
        "#### Step 3.5 - 创业板20cm预启动观察池",
        "> **核心问题**：哪些创业板20cm样本正在出现“均线粘合 + 蛇形走位 + K线呼吸感”，值得先保留观察权？",
        "> **纪律**：这里只先进观察池，不直接给执行权；必须等后续右侧确认后，才评估是否升级到30%条件试错。",
    ]
    if filtered_out_gem_candidates:
        filtered_text = "；".join(
            f"{item.get('name', '-')}({item.get('code', '-')})/{item.get('sector', '-')}：{item.get('filtered_reason', '-') or '-'}"
            for item in filtered_out_gem_candidates[:4]
        )
        lines.append(f"> **主线过滤提示**：当前有20cm预启动样本，但因非主线被过滤：{filtered_text}")
    lines.append("")
    if not gem_observation_stocks:
        return lines
    lines.extend(["| 股票 | 层级 | 预启动说明 | 观察动作 |", "|------|------|------------|----------|"])
    for item in gem_observation_stocks:
        lines.append(
            f"| {item.get('name', '-')}({item.get('code', '-')}) | {item.get('tier', '-') or item.get('core_level', '-')} | "
            f"{item.get('note', item.get('abnormal_summary', '-'))} | {item.get('watch_anchor_note', item.get('tmr_forecast', '-'))} |"
        )
    lines.append("")
    return lines


def render_market_research_snapshot_section(context):
    context = context or {}
    compact = bool(context.get("compact"))
    observation = context.get("observation") or {}
    benchmark_change = float(context.get("benchmark_change", 0) or 0)
    turnover = float(context.get("turnover", 0) or 0)
    if compact:
        lines = [
            "### 🔬 市场研究快照",
            f"- **盘面风险偏好**: 上证{benchmark_change:+.2f}% / 涨停{observation.get('zt_count', 0)} / 跌停{observation.get('dt_count', 0)} / 涨跌比{observation.get('rise_fall_ratio_text', '暂无')} / 成交额{turnover:.0f}亿",
            f"- **主线焦点**: {context.get('competition_result', '主线待定')}；{context.get('competition_evidence', '先看趋势密度、异常承接和资金聚焦谁先胜出')}",
            f"- **风格背景**: {context.get('style_label', '-') }；{context.get('style_reason', '-')}",
            f"- **异常承接证据**: {context.get('abnormal_projection_label', '-')}；{context.get('abnormal_projection_reason', '-')}",
            f"- **明天能不能开仓**: {context.get('follow_verdict_label', '-')}；{context.get('follow_verdict_reason', '-')}",
            f"- **统一状态判断**: {context.get('state_energy', '-')}；{context.get('state_reason', '-')}；{context.get('state_flow_direction', '-')}",
            "",
        ]
        return lines

    lines = [
        "### 🔬 市场研究快照",
        "| 证据环节 | 当前证据 | 推导判断 | 对动作的作用 |",
        "|----------|----------|----------|--------------|",
        (
            f"| 盘面风险偏好 | 热点/趋势/异常 | 上证{benchmark_change:+.2f}% / 涨停{observation.get('zt_count', 0)} / "
            f"跌停{observation.get('dt_count', 0)} / 涨跌比{observation.get('rise_fall_ratio_text', '暂无')} / 成交额{turnover:.0f}亿 | "
            "先看风险偏好，再决定能否继续往下判断 |"
        ),
        f"| 主线焦点 | {context.get('competition_result', '主线待定')} | {context.get('competition_evidence', '先看趋势密度、异常承接和资金聚焦谁先胜出')} | 优先聚焦主线对象 |",
        f"| 主线内部轮动 | {context.get('rotation_label', '-')} | {context.get('rotation_summary_text', '-') or context.get('rotation_reason', '-')} | {context.get('rotation_action', '-')} |",
        f"| 叙事节点 | {context.get('narrative_label', '-')} | {context.get('narrative_reason', '-')} | {context.get('narrative_action', '-')} |",
        f"| 风格背景 | {context.get('style_label', '-')} | {context.get('style_evidence_text', '-') or context.get('style_reason', '-')} | 背景参考，不直接触发动作 |",
        f"| 异常承接证据 | {context.get('abnormal_projection_label', '-')} | {context.get('abnormal_projection_reason', '-')} | 允许继续进入下一步判断 |",
        f"| 明天能不能开仓 | {context.get('follow_verdict_label', '-')} | {context.get('follow_verdict_reason', '-')} | 动作锚定到“明天能不能开仓” |",
        "",
        f"- **统一状态判断**: {context.get('state_energy', '-')}；{context.get('state_reason', '-')}；{context.get('state_flow_direction', '-')}",
        f"- **龙头记忆**: 已保留{observation.get('leader_memory_count', 0)}只记忆资产，其中可信记忆{observation.get('trusted_tracking_count', 0)}只",
    ]
    if observation.get("densest_sector"):
        lines.append(f"- **最强趋势密度**: {observation.get('densest_sector')} 当前有{observation.get('densest_sector_trend_count', 0)}只活跃趋势股")
    if context.get("style_reason"):
        lines.append(f"- **风格说明**: {context.get('style_reason')}")
    dialectical_decision = context.get("dialectical_decision") or {}
    if dialectical_decision:
        lines.extend(
            [
                "### 🧠 辩证决策补充",
                f"- **现在更像什么阶段**: {dialectical_decision.get('stage_label', '-')}；{dialectical_decision.get('stage_reason', '-')}",
                f"- **指数和赚钱效应是否背离**: {dialectical_decision.get('index_profit_relation', '-')}；{dialectical_decision.get('index_profit_reason', '-')}",
                f"- **赚钱效应现在往哪聚**: {dialectical_decision.get('focus_label', '-')}；{dialectical_decision.get('focus_action', '-')}",
                f"- **明天优先看哪类对象**: {dialectical_decision.get('candidate_focus', '-')}；{dialectical_decision.get('candidate_action', '-')}",
                f"- **什么情况下先不认这轮修复**: {' / '.join(dialectical_decision.get('falsification_conditions', []) or ['暂无'])}",
            ]
        )
    lines.append("")
    return lines


def render_step0_follow_section(context):
    context = context or {}
    if context.get("compact"):
        return [
            f"**明日裁决**: {context.get('step0_prediction_cn', '-')}",
            f"**裁决依据**: {context.get('step0_reason', '-')}",
            f"**开盘前动作**: {context.get('step0_action', '-')}",
            f"**盘面风险偏好**: 上证{context.get('zt_count', 0)} / 跌停{context.get('dt_count', 0)}；{context.get('observation_summary', '-')}",
            f"**主线焦点**: {context.get('densest_sector', '暂无明确主线')}；趋势股{context.get('densest_sector_trend_count', 0)}只",
            f"**异常承接**: {context.get('resilient_abnormal_count', 0)}强 / {context.get('failed_abnormal_count', 0)}弱；{context.get('abnormal_projection_label', '-')}",
            f"**最终状态判断**: {context.get('state_energy', '-') }；{context.get('state_reason', '-')}",
            "",
            f"> **Step 0 结论**: {context.get('step0_reason', '-')}",
            "",
        ]
    lines = [
        f"**明日裁决**: {context.get('step0_prediction_cn', '-')}",
        f"**裁决依据**: {context.get('step0_reason', '-')}",
        f"**开盘前动作**: {context.get('step0_action', '-')}",
        "",
        "| 证据环节 | 当前证据 | 推导判断 | 对动作的作用 |",
        "|----------|----------|----------|--------------|",
        f"| 盘面风险偏好 | {context.get('zt_count', 0)} / {context.get('dt_count', 0)} | {context.get('observation_summary', '-')} | 先看风险偏好，再决定能否继续往下判断 |",
        f"| 风格背景 | {context.get('style_label', '-')} | {context.get('style_reason', '-')} | 背景参考，不直接触发动作 |",
        f"| 主线焦点 | {context.get('densest_sector', '暂无明确主线')} | 趋势密度最强方向为{context.get('densest_sector', '待确认')}，活跃趋势股{context.get('densest_sector_trend_count', 0)}只 | 优先聚焦主线对象 |",
        f"| 异常承接证据 | {context.get('resilient_abnormal_count', 0)}强 / {context.get('failed_abnormal_count', 0)}弱 | {context.get('abnormal_projection_label', '-')} | 允许继续进入下一步判断 |",
        f"| 最终状态判断 | {context.get('state_energy', '-')} | {context.get('state_reason', '-')} | 动作锚定到“开盘前动作” |",
        "",
        f"> **Step 0 结论**: {context.get('step0_reason', '-')}",
        "> **⚠️ 重要提醒**: Step 0 不再单独猜市场，而是直接引用统一市场研究快照；明日前30分钟先确认环境，真正买点一律等60分钟K线确认；买入后再用30分钟结构定止损。",
        "",
        "",
    ]
    return lines
