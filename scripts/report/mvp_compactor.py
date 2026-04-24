DEFAULT_STAGE_META = {
    "environment_follow": {
        "label": "Step 0",
        "title": "明日环境与跟随裁决",
    },
    "watch_pool": {
        "label": "Step 1",
        "title": "明天观察池",
    },
}


def _find_report_line_index(lines, marker, start=0, match_mode="equals"):
    for idx in range(start, len(lines)):
        line = lines[idx]
        if match_mode == "equals" and line == marker:
            return idx
        if match_mode == "startswith" and line.startswith(marker):
            return idx
        if match_mode == "contains" and marker in line:
            return idx
    return -1


def _remove_report_section(lines, start_marker, end_marker=None, start_mode="equals", end_mode="equals"):
    start_idx = _find_report_line_index(lines, start_marker, match_mode=start_mode)
    if start_idx < 0:
        return lines
    if end_marker is None:
        del lines[start_idx:]
        return lines
    end_idx = _find_report_line_index(lines, end_marker, start=start_idx + 1, match_mode=end_mode)
    if end_idx < 0:
        del lines[start_idx:]
    else:
        del lines[start_idx:end_idx]
    return lines


def _squeeze_report_blank_lines(lines):
    squeezed = []
    blank_count = 0
    for line in lines:
        if line == "":
            blank_count += 1
            if blank_count > 1:
                continue
        else:
            blank_count = 0
        squeezed.append(line)
    return squeezed


def _resolve_stage_heading(stage_lookup, stage_key):
    stage_meta = dict(DEFAULT_STAGE_META.get(stage_key, {}))
    stage_meta.update(stage_lookup.get(stage_key, {}) if isinstance(stage_lookup, dict) else {})
    label = str(stage_meta.get("label", "") or DEFAULT_STAGE_META.get(stage_key, {}).get("label", "")).strip()
    title = str(stage_meta.get("title", "") or DEFAULT_STAGE_META.get(stage_key, {}).get("title", "")).strip()
    if not label or not title:
        return ""
    return f"#### {label} - {title}"


def build_mvp_compaction_rules(stage_lookup=None):
    stage_lookup = stage_lookup or {}
    return [
        ("## 二、预期日历（AI智能分析板块）", "## 十三、统一执行链（狙击手视角）", "equals", "equals"),
        ("### 总-市场整体判断", _resolve_stage_heading(stage_lookup, "environment_follow"), "equals", "equals"),
        (_resolve_stage_heading(stage_lookup, "watch_pool"), "#### 最终结论", "equals", "equals"),
        ("#### 💡 核心交易哲学：看好A，干A！", "## 十四、AI市场洞察总结", "equals", "equals"),
        ("## 十四、AI市场洞察总结", "## 十五、策略计划账本", "equals", "equals"),
        ("#### 💡 主线执行纪律", "## 十四、市场快照", "equals", "equals"),
        ("## 十四、市场快照", "## 十五、策略计划账本", "equals", "equals"),
        ("#### 1.1 冻结因子快照", "### 2. 最近计划回放", "equals", "equals"),
        ("### 5. 固定Setup信号库回顾", "### 7. 系统自校准建议", "equals", "equals"),
        ("### 8. 跨结构周期毕业看板", "## 附录：数据获取与执行步骤清单", "equals", "equals"),
        ("## 附录：数据获取与执行步骤清单", None, "equals", "equals"),
    ]


def compact_report_for_mvp(report, *, stage_lookup=None):
    compacted = list(report or [])
    for start_marker, end_marker, start_mode, end_mode in build_mvp_compaction_rules(stage_lookup=stage_lookup):
        if not start_marker:
            continue
        compacted = _remove_report_section(
            compacted,
            start_marker,
            end_marker=end_marker,
            start_mode=start_mode,
            end_mode=end_mode,
        )

    compacted = [
        "## 二、统一执行链" if line == "## 十三、统一执行链（狙击手视角）" else
        "## 三、策略计划账本" if line == "## 十五、策略计划账本" else
        line
        for line in compacted
    ]
    return _squeeze_report_blank_lines(compacted)
