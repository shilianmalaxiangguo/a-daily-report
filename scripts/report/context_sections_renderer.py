def render_mainline_discipline_section(mainline_name):
    mainline_name = str(mainline_name or "").strip()
    if not mainline_name:
        return []
    return [
        "#### 💡 核心交易哲学：看好A，干A！",
        f"> **主线**: {mainline_name}",
        "",
        "**为什么只看主线，不做B/C？**",
        "1. **龙头效应**: 市场资金聚焦主线，边缘板块流动性差",
        "2. **时间成本**: A涨的时候B未必跟涨，但A跌的时候B一定先跌",
        "3. **确定性**: 主线有板块效应支撑，个股更安全；边缘板块缺乏支撑",
        "",
        f"**今日纪律**: 认准'{mainline_name}'，就在'{mainline_name}'里找机会，绝不被'相关概念'分散火力！",
        "",
    ]


def render_supplementary_perspective_section(perspective_text):
    perspective_text = str(perspective_text or "").strip()
    if not perspective_text:
        return []
    lines = [
        "## 十三点五、补充视角（复盘参考）",
        "> *以下为复盘时补充的市场观点，供交叉验证参考*",
        "",
    ]
    lines.extend(perspective_text.split("\n"))
    lines.append("")
    return lines


def render_ai_market_insight_section(context):
    context = context or {}
    return [
        "## 十四、AI市场洞察总结",
        f"- **核心特征**: {context.get('market_trend', '未知')}，涨停{int(context.get('zt_count', 0) or 0)}只，跌停{int(context.get('dt_count', 0) or 0)}只",
        f"- **能量状态**: {context.get('energy_state', '未知')} - {context.get('flow_direction', '-')}",
        f"- **资金主线**: {context.get('mainline_text', '暂无明确主线')}",
        f"- **风险点**: {context.get('risk_text', '暂无明确风险')}",
        f"- **关注重点**: {context.get('focus_text', '市场整体持续性，量能变化，板块轮动')}",
        "",
    ]
