from __future__ import annotations

import datetime
import html
import json
import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from report.surface_wording import find_legacy_surface_wording

LEGACY_TRADING_TIME_WORDING_MARKERS = (
    "60" + "分钟" + "确认",
    "60 " + "分钟" + "确认",
    "首个60" + "分钟",
    "10" + "点确认",
    "10" + "点承接",
    "10" + "点后",
    "10" + "点附近",
    "10" + "点前后",
    "10" + "点左右",
    "10:00" + "左右买",
    "10:00" + "左右观察",
    "尾盘" + "开新仓",
    "尾盘" + "新增参与",
    "09:50-10:10" + "承接确认",
    "09:50-10:10" + "二次确认",
    "09:50-10:10" + "确认",
    "形成" + "参与窗口后",
    "60" + "分钟结构确认",
    "60" + "分钟缠论确认",
    "60" + "分钟走势类型",
    "60" + "分钟定买点",
    "60" + "分钟再转强",
    "30" + "分钟定止损",
    "30" + "分钟结构失守",
    "30" + "分钟结构止损线",
    "09:35-10:30",
    "10:30-14:30",
    "结构确认窗口",
    "盘中执行（10:30-14:30）",
    "分钟" + "确认",
    "参与窗口" + "分层确认",
    "参与窗口" + "确认",
    "参与窗口" + "成立",
    "参与窗口" + "命中",
    "预演" + "参与窗口",
    "形成" + "参与窗口",
    "参与窗口" + "失败",
    "参与窗口" + "不成立",
    "参与窗口" + "才",
)

PROCESS_EVIDENCE_TITLES = (
    "主线内观察候选",
    "明日次核心预判",
    "跨线观察候选",
    "重点观察名单",
    "重点观察复核脚本",
    "历史过程观察样本去向",
    "过程观察25日跟踪表",
    "明日极度看好近25日跟踪表",
    "重点观察历史回测表",
    "明日观察池",
    "明天观察池",
    "异动后观察池",
    "跟踪记忆校验",
    "主线趋势密度复核",
    "当前个股观察监控池",
    "观察对象生命周期表",
    "逐只预判明日风险",
    "明日风险分组",
    "板块级明日风险预判",
    "明天先观察组",
    "明天重点候选组",
    "明日继续观察",
    "明日观察位预计算表",
    "今日总决策面板",
    "候选主表",
    "最终标的传导链",
    "狙击手最终标的完整路径图",
    "候选选股轨迹",
    "候选选股轨迹明细",
)

FRONT_PAGE_HEADINGS = [
    "## 二、市场基底",
    "## 三、周期与主线",
    "## 明日账户建议",
    "## 一、交易纪律",
    "## 四、资金意图",
    "## 五、个股解读",
    "## 六、明日执行计划",
    "## 七、最终结论",
]

APPENDIX_HEADING = "## 八、详细附录"

REQUIRED_EXECUTION_WINDOWS = [
    "09:30-09:35",
    "09:50-10:10",
    "14:30-14:55",
]

ZERO_POSITION_REQUIRED_EXECUTION_WINDOWS = [
    "09:30-09:35",
    "09:50-10:10",
    "14:30-14:55",
]

REQUIRED_EXECUTION_CONDITIONS = [
    ("09:50-10:10窗口", ("09:50-10:10窗口",)),
    (
        "固定交易窗口条件",
        (
            "固定交易窗口",
            "09:30-09:35",
            "09:50-10:10窗口",
            "竞价表态",
            "开盘前几分钟",
            "回封",
            "打板",
        ),
    ),
    ("失效价 / 单笔-5%底线", ("失效价", "单笔-5%")),
    ("不参与 / 不做 / 空仓", ("不参与", "不做", "不开新仓", "空仓")),
]

APPENDIX_DUPLICATE_FRONT_PAGE_HEADINGS = {
    "附录：一、交易纪律",
    "附录：二、市场基底",
    "附录：三、周期与主线",
    "附录：四、资金意图",
    "附录：五、个股解读",
    "附录：六、明日执行计划",
    "附录：七、最终结论",
}

DEGRADED_MARKERS = (
    "missing_dependency",
    "degraded",
    "source_status",
    "数据缺失",
    "数据不足",
    "降级",
    "缺失",
)

NO_TRADE_MARKERS = ("不做", "不开新仓", "空仓等待")

UNIQUE_FOCUS_EVIDENCE_FAMILIES = [
    ("主线一致性", ("主线", "周期主线", "当天主攻线")),
    ("承接", ("承接",)),
    ("资金痕迹", ("资金", "资金痕迹")),
    ("09:50-10:10窗口", ("09:50-10:10窗口",)),
    ("排除/不做兜底", ("不满足", "不做", "不开新仓", "排除")),
]

ZERO_POSITION_UNIQUE_FOCUS_EVIDENCE_FAMILIES = [
    ("主线一致性", ("主线", "周期主线", "当天主攻线")),
    ("承接", ("承接",)),
    ("资金痕迹", ("资金", "资金痕迹")),
    ("观察窗口", ("观察窗", "观察窗口", "09:50-10:10")),
    ("排除/不做兜底", ("不满足", "不做", "不新增参与", "排除")),
]

UNIQUE_FOCUS_BUY_LABELS = ("唯一买入", "可执行候选", "买入")
UNIQUE_FOCUS_OBSERVATION_ONLY_MARKERS = (
    "只看，不买",
    "不给买入指令",
    "不构成买入指令",
    "仅观察",
    "只观察",
    "观察",
    "不买",
    "不直接给资格",
    "不直接给买入资格",
    "条件未满足",
    "等09:50-10:10窗口条件",
    "待确认",
    "不开新仓",
    "不做",
)

REASONING_SURFACE_HEADING = "### 0. 推理裁决"
REASONING_REQUIRED_LABELS = ("结论", "关键证据", "触发条件", "失败条件", "排除对象", "推理深度")
REASONING_CHAIN_LEAK_MARKERS = ("chain-of-thought", "思维链", "完整推理链", "隐藏推理")
SIMULATION_NOISE_MARKERS = (
    "MiroFish",
    "mirofish",
    "多智能体",
    "多智能体一致认为",
    "多智能体共识",
    "沙盘推演",
    "沙盘推演显示",
    "某情景下可能爆发",
    "模型认为胜率提高",
    "综合模拟后建议买入",
    "虽然规则未满足，但推演偏乐观",
)
THEORY_ACTION_MARKERS = (
    "能量释放，所以可以买",
    "能量释放，所以可以加仓",
    "能量释放，所以提高仓位",
    "群体行为共振，所以可以买",
    "群体行为共振，所以可以加仓",
    "群体行为共振，所以提高仓位",
)

THEORY_CONCEPT_TERMS = ("能量学", "能量释放", "群体行为")
THEORY_ACTION_CONTEXT_MARKERS = ("买", "加仓", "仓位", "候选资格", "资格")

THEORY_NOISE_MARKERS = (
    "能量学判断",
    "能量释放完成",
    "群体行为共振",
)


def _m(*parts):
    return "".join(parts)


LEGACY_POSITION_STYLE_MARKERS = (
    "空仓 / 短线确认",
    "空仓 / 短线 / 波段 / 尾盘量化例外",
    _m("50%执行", "30%"),
    _m("A-档", "50%"),
    _m("A", "档", "80%", "-100%"),
    _m("3", "0%", "条件", "试错"),
    _m("ABC", "档"),
    _m("A", "档"),
    _m("B", "档"),
    _m("C", "档"),
    _m("一", "档"),
    _m("二", "档"),
    _m("三", "档"),
)
POSITION_STYLE_GRADE_MARKERS = ("0%不参与", "50%条件执行", "100%核心进攻")
LEGACY_OBSERVATION_SURFACE_MARKERS = (
    _m("观察", "锚"),
    _m("观察", "锚点"),
    _m("观察优先", "锚点"),
    _m("最终观察", "锚"),
    _m("只看观察", "锚"),
)
ZERO_POSITION_ACTION_MARKERS = ("明日主买对象", "明日补位对象", "新增参与", _m("条件", "50%"), "50%条件执行", "才评估50%条件执行")
ZERO_POSITION_CURRENT_DECISION_ACTION_LABELS = ("主买对象", "补位对象")
ZERO_POSITION_LEGACY_TOMORROW_WORDING_MARKERS = (
    "明日可能反包",
    "关注埋伏",
    "明日买点预计算",
    "买入窗口",
    "买点窗口",
    "买点质量",
    "买点线",
    "可执行爆发",
    "真正可执行对象",
    "新仓止损",
    "回封/打板",
    _m("条件", "50%"),
    "50%条件执行",
    "才评估50%条件执行",
    "观察唯一对象",
    "按09:30-09:35窗口处理",
    "本时段只确认主线核心是否在固定交易窗口内满足条件",
)
MONTHLY_RHYTHM_HEADING = "### 月度攻防与进攻仓位"
MONTHLY_RHYTHM_REQUIRED_LABELS = ("本月模式", "当月收益", "盈利垫", "进攻仓位三态", "明日最大仓位")
POSITION_ATTACK_GRADE_LABELS = {"0%", "50%", "100%"}
POSITION_ATTACK_GRADE_MIN_POSITION = {
    "0%": 0,
    "50%": 50,
    "100%": 100,
}
LEGACY_CANDIDATE_SECTION_TITLES = ("### 1. 主线内观察候选", "### 1. 主线内可执行候选", "### 2. 跨线观察候选")
MAINLINE_CAPACITY_REGIME_HEADING = "### 4. 主线容量与格局判断"
MAINLINE_CAPACITY_REGIME_HEADER = "| 主线容量 | 主线格局 | 主攻线 | 竞争线/背景线 | 主线确认依据 | 板块关系状态 | 主线进程 | 明日动作 |"
LEGACY_DOUBLE_MAINLINE_HEADER = "| 周期主线 | 当天主攻线 | 两者关系 | 明日动作 |"
MAINLINE_ATTACK_EVIDENCE_HEADING = "#### 主线攻击证据"
MAINLINE_ATTACK_EVIDENCE_HEADER = "| 板块 | 攻击状态 | 净流入排名 | 净流入 | 涨停数 | 高标高度 | 成交占比变化 | 结论 |"
TOP50_TURNOVER_HEADER = "| 日期 | Top50占比 | 状态 | 较前日 | Top50成交额 | 两市成交额 |"
MAINLINE_TURNOVER_HEADER = "| 日期 | 小周期方向 | 主线成交额 | 两市成交额 | 占比 | 占比变化 | 切换判断 | 解读 |"
PRICE_BAND_STYLE_HEADING = "### 3. 价格带风格"
PRICE_BAND_STYLE_HEADER = "| 日期 | 百元股涨跌幅 | 低价股涨跌幅 | 当日差值 | 相对风格 | 绝对状态 |"
NEW_HIGH_FEEDBACK_HEADING = "### 3. 创新高趋势反馈"
MARKET_STATUS_HEADING = "### 2. 市场状态结论"
MARKET_STATUS_HEADER = "| 项目 | 结论 | 依据 |"
MARGIN_PRESSURE_FRONT_HEADER = "| 日期 | 融资余额 | 两市成交额 | 融资承接比 | 状态 |"
MARGIN_PRESSURE_APPENDIX_HEADER = "| 日期 | 融资余额 | 两市成交额 | 融资承接比 | 压力差 | 状态 | 较前日 |"
EXTREME_CONVICTION_TRACKING_HEADING = "**明日极度看好近25日跟踪表**"
EXTREME_CONVICTION_TRACKING_HEADER = "| 入选日 | 股票 | 代码 | 排名 | 所属方向 | 观察位窗口 | 复盘状态 | 历史复盘动作 | 作废线 | 记录ID |"
NEW_STOCK_VISIBILITY_HEADING = "### 附录A：新股周期判定"
NEW_STOCK_VISIBILITY_MARKERS = (
    "有新股研究升级，进入观察。",
    "有新股研究池，但今日未形成买入资格。",
    "新股研究池为空，今日不参与。",
    "上市日期缺失，不参与。",
)
__all__ = ["audit_new_stock_visibility", "audit_report_markdown"]

CHANLUN_TOMORROW_DECISION_HEADING = "明日抉择"
CHANLUN_ZERO_POSITION_ACTION_MARKERS = ("空仓等待", "不参与", "不新增参与", "禁止参与")
STOPPED_REPORT_REQUIRED_MARKERS = (
    "关键数据不完整，停止生成",
    "不生成日报",
    "不给明日策略",
    "不给个股执行计划",
)
STOPPED_REPORT_TRADE_PLAN_MARKERS = (
    "明日账户建议",
    "T0主对象",
    "T0备用",
    "最终动作表",
    "确认后执行预案",
    "明天具体怎么做",
)
ZERO_POSITION_POSITIVE_PARTICIPATION_MARKERS = (
    "勉强可参与",
    "谨慎参与",
    "寻找参与资格",
    "找参与资格",
    "恢复参与资格",
    "提高参与资格",
    "提高参与质量",
)
ZERO_POSITION_ALLOWED_PARTICIPATION_MARKERS = (
    "不参与",
    "不新增参与",
    "不能转成新增参与",
    "暂无新增参与资格",
    "没有可买对象",
    "没有合格参与对象",
    "不构成明日新增参与",
    "不作为明日新增参与依据",
    "最终0%时只作观察样本",
    "只展示真正具备参与资格的对象",
)
ZERO_POSITION_STRONG_BASIS_MARKERS = (
    "弱市场",
    "冰点",
    "趋势失效",
    "关键数据不完整",
    "数据缺口",
    "账户买不了",
    "买不了一手",
    "只处理旧仓",
    "降风险",
    "逆势攻击",
    "放量下杀",
    "退潮",
    "高波动",
)
ZERO_POSITION_WEAK_BASIS_MARKERS = (
    "市场条件未到",
    "只保留观察对象",
    "只保留观察对象",
    "当前只有观察权",
    "等待确认",
)
OPPORTUNITY_COMPARISON_HEADING = "## 旧仓与新机会风险价格对比"
OLD_POSITION_COMPARISON_ROLE_MARKERS = ("old_position", "failed_entry", "trend_holding", "旧仓")
INCOMPLETE_OPPORTUNITY_RISK_MARKERS = ("", "-", "待计算", "不合格", "缺失", "待补")


def _finding(code, message, line=None):
    result = {"code": code, "message": message}
    if line is not None:
        result["line"] = line
    return result


def _lines(markdown):
    return str(markdown or "").splitlines()


def _front_page_lines(lines):
    front = []
    for line in lines:
        if line == APPENDIX_HEADING:
            break
        front.append(line)
    return front


def _report_target_date(lines):
    for line in lines:
        match = re.search(r"#\s*(\d{4}-\d{2}-\d{2})\s+a股市场分析", str(line or ""), re.I)
        if match:
            return match.group(1)
    return ""


def _date_gap_days(later_date, earlier_date):
    try:
        later = datetime.datetime.strptime(str(later_date or ""), "%Y-%m-%d").date()
        earlier = datetime.datetime.strptime(str(earlier_date or ""), "%Y-%m-%d").date()
    except ValueError:
        return None
    return (later - earlier).days


def _appendix_lines(lines):
    for index, line in enumerate(lines):
        if line == APPENDIX_HEADING:
            return lines[index + 1 :]
    return []


def _section_after(lines, start_marker):
    try:
        start = list(lines).index(start_marker)
    except ValueError:
        return []
    section = []
    for line in list(lines)[start + 1 :]:
        text = str(line)
        if text.startswith("## ") or text.startswith("### "):
            break
        section.append(line)
    return section


def _split_md_row(line):
    text = str(line or "").strip()
    if not text.startswith("|"):
        return []
    return [cell.strip() for cell in text.strip("|").split("|")]


def _parse_percent_int(value):
    match = re.search(r"-?\d+(?:\.\d+)?", str(value or ""))
    if not match:
        return None
    try:
        return int(float(match.group(0)))
    except ValueError:
        return None


def _is_separator_cells(cells):
    joined = "".join(cells).replace(" ", "")
    return bool(joined) and set(joined) <= {"-", ":"}


def _clean_html_cell(value):
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
    return re.sub(r"\s+", " ", text).strip()


def _extract_chanlun_tomorrow_decision_values(companion_html):
    text = str(companion_html or "")
    heading_match = re.search(r"<h2\b[^>]*>\s*明日抉择\s*</h2>", text, re.I)
    if not heading_match:
        return None
    table_match = re.search(r"<table\b[^>]*>(.*?)</table>", text[heading_match.end() :], re.I | re.S)
    if not table_match:
        return {}
    values = {}
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", table_match.group(1), re.I | re.S):
        cells = re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", row, re.I | re.S)
        if len(cells) < 2:
            continue
        label = _clean_html_cell(cells[0])
        value = _clean_html_cell(cells[1])
        if label:
            values[label] = value
    return values


def _extract_elimination_tournament_payload(companion_html):
    text = str(companion_html or "")
    if "elimination-tournament" not in text and "明日标的选股淘汰赛" not in text:
        return None
    match = re.search(
        r'<script\b[^>]*id=["\']elimination-payload["\'][^>]*>(?P<payload>.*?)</script>',
        text,
        re.I | re.S,
    )
    if not match:
        return {}
    payload_text = html.unescape(match.group("payload")).strip()
    if not payload_text:
        return {}
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _extract_sector_capital_preflight_payload(companion_html):
    text = str(companion_html or "")
    if "sector-capital-preflight" not in text and "板块资金扩散生成前复核" not in text:
        return None
    match = re.search(
        r'<script\b[^>]*id=["\']sector-capital-preflight-payload["\'][^>]*>(?P<payload>.*?)</script>',
        text,
        re.I | re.S,
    )
    if not match:
        return {}
    payload_text = html.unescape(match.group("payload")).strip()
    if not payload_text:
        return {}
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _audit_companion_final_action_consistency(lines, payload, *, artifact_label, missing_code, conflict_code):
    if payload is None:
        return None
    if not payload:
        return [
            _finding(
                missing_code,
                f"{artifact_label} companion HTML is missing readable payload",
            )
        ]
    front = _front_page_lines(lines)
    final_action = payload.get("final_action") if isinstance(payload.get("final_action"), dict) else {}
    final_target = final_action.get("target") if isinstance(final_action.get("target"), dict) else {}
    final_identity = _target_identity(
        final_target.get("code") or final_target.get("name") or ""
    )
    final_pct = _parse_percent_int(str(final_action.get("position_pct", "")))
    if final_pct is None:
        final_pct = _parse_percent_int(final_action.get("label", ""))
    if _final_summary_is_zero_position(front):
        if (final_pct or 0) == 0 and not final_identity:
            return []
        return [
            _finding(
                conflict_code,
                f"final summary is 0%不参与, but {artifact_label} companion HTML contains a positive final action",
            )
        ]
    front_target = _extract_final_unique_target(front)
    front_identity = _target_identity(front_target)
    front_pct = _parse_percent_int(_extract_final_execution_style(front))
    if front_pct is not None and final_pct is not None and front_pct != final_pct:
        return [
            _finding(
                conflict_code,
                f"front-page final position {front_pct}% conflicts with {artifact_label} companion HTML final position {final_pct}%",
            )
        ]
    if front_identity and not final_identity and (front_pct or 0) > 0:
        return [
            _finding(
                conflict_code,
                f"front-page final target {front_target} is missing from {artifact_label} companion HTML final action",
            )
        ]
    if front_identity and final_identity and front_identity != final_identity:
        return [
            _finding(
                conflict_code,
                f"front-page final target {front_target} conflicts with {artifact_label} companion HTML final target {final_identity}",
            )
        ]
    return []


def _audit_elimination_tournament_consistency(lines, companion_html):
    return _audit_companion_final_action_consistency(
        lines,
        _extract_elimination_tournament_payload(companion_html),
        artifact_label="elimination",
        missing_code="elimination_tournament_payload_missing",
        conflict_code="elimination_tournament_final_conflict",
    )


REQUIRED_SECTOR_CAPITAL_PREFLIGHT_LAYERS = (
    "market_capital_structure",
    "sector_capital_diffusion",
    "capital_carrier",
    "carrier_role",
    "quant_trace",
    "price_action",
    "cycle_probability_window",
    "counter_evidence_account",
    "final_action",
)


REQUIRED_SECTOR_CAPITAL_PREFLIGHT_DECISIONS = (
    "市场能否进攻",
    "哪个板块被选择",
    "谁是资金载体",
    "是否有量化参与痕迹",
    "价格行为是否接受",
    "周期概率窗口是否打开",
    "账户是否适配",
)


def _audit_sector_capital_preflight_payload_contract(payload):
    if payload is None or not payload:
        return []
    findings = []
    if payload.get("derivation_contract") != "sector_capital_diffusion_first.v1":
        findings.append(
            _finding(
                "sector_capital_preflight_contract_missing",
                "sector capital preflight payload is missing sector-capital-first derivation contract",
            )
        )
    mermaid = str(payload.get("mermaid") or "")
    for text in ("周期概率窗口", "唯一明日动作或不参与", "白痴指数复核", "压缩/合并/降级低价值高成本层"):
        if text not in mermaid:
            findings.append(
                _finding(
                    "sector_capital_preflight_mermaid_incomplete",
                    f"sector capital preflight Mermaid is missing: {text}",
                )
            )
    layers = payload.get("layers") if isinstance(payload.get("layers"), list) else []
    layer_ids = [str(layer.get("id") or "") for layer in layers if isinstance(layer, dict)]
    missing_layers = [layer_id for layer_id in REQUIRED_SECTOR_CAPITAL_PREFLIGHT_LAYERS if layer_id not in layer_ids]
    if missing_layers:
        findings.append(
            _finding(
                "sector_capital_preflight_layers_missing",
                "sector capital preflight payload is missing layers: " + ", ".join(missing_layers),
            )
        )
    for layer in layers:
        if not isinstance(layer, dict):
            continue
        entries = layer.get("entries") if isinstance(layer.get("entries"), list) else []
        eliminated = [entry for entry in entries if isinstance(entry, dict) and entry.get("status") == "eliminated"]
        survivors = [entry for entry in entries if isinstance(entry, dict) and entry.get("status") == "survived"]
        if int(layer.get("input_count") or 0) != len(entries):
            findings.append(
                _finding(
                    "sector_capital_preflight_layer_count_mismatch",
                    f"sector capital preflight layer {layer.get('id')} input_count does not match entries",
                )
            )
        if int(layer.get("eliminated_count") or 0) != len(eliminated):
            findings.append(
                _finding(
                    "sector_capital_preflight_layer_count_mismatch",
                    f"sector capital preflight layer {layer.get('id')} eliminated_count does not match entries",
                )
            )
        if int(layer.get("survivor_count") or 0) != len(survivors):
            findings.append(
                _finding(
                    "sector_capital_preflight_layer_count_mismatch",
                    f"sector capital preflight layer {layer.get('id')} survivor_count does not match entries",
                )
            )
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if entry.get("status") == "final_action":
                continue
            missing_entry_fields = [
                key
                for key in ("stock_code", "stock_name", "sector", "status", "reason", "next_basis", "elimination_basis")
                if key not in entry
            ]
            if missing_entry_fields:
                findings.append(
                    _finding(
                        "sector_capital_preflight_entry_fields_missing",
                        f"sector capital preflight layer {layer.get('id')} entry is missing fields: "
                        + ", ".join(missing_entry_fields),
                    )
                )
    decision_list = payload.get("decision_list") if isinstance(payload.get("decision_list"), list) else []
    decision_items = [str(item.get("item") or "") for item in decision_list if isinstance(item, dict)]
    missing_decisions = [item for item in REQUIRED_SECTOR_CAPITAL_PREFLIGHT_DECISIONS if item not in decision_items]
    if missing_decisions:
        findings.append(
            _finding(
                "sector_capital_preflight_decision_list_missing",
                "sector capital preflight decision list is missing: " + ", ".join(missing_decisions),
            )
        )
    idiot_rows = payload.get("idiot_index_review") if isinstance(payload.get("idiot_index_review"), list) else []
    if not idiot_rows:
        findings.append(
            _finding(
                "sector_capital_preflight_idiot_index_missing",
                "sector capital preflight payload is missing idiot-index review rows",
            )
        )
    return findings


def _audit_sector_capital_preflight_consistency(lines, companion_html):
    payload = _extract_sector_capital_preflight_payload(companion_html)
    findings = _audit_companion_final_action_consistency(
        lines,
        payload,
        artifact_label="sector capital preflight",
        missing_code="sector_capital_preflight_payload_missing",
        conflict_code="sector_capital_preflight_final_conflict",
    )
    if findings is None:
        return None
    findings.extend(_audit_sector_capital_preflight_payload_contract(payload))
    return findings


def _audit_front_page_headings(lines):
    findings = []
    front = _front_page_lines(lines)
    headings = [line for line in front if line in FRONT_PAGE_HEADINGS]
    if headings != FRONT_PAGE_HEADINGS:
        findings.append(
            _finding(
                "front_page_heading_order",
                "front page headings must appear exactly once in canonical order before appendices",
            )
        )
    for heading in FRONT_PAGE_HEADINGS:
        if headings.count(heading) > 1:
            findings.append(_finding("duplicate_front_page_heading", f"duplicated front-page heading: {heading}"))
    return findings


def _extract_execution_window_labels(lines):
    labels = []
    in_window_table = False
    for line in _front_page_lines(lines):
        cells = _split_md_row(line)
        if cells and cells[0] == "时间窗口":
            in_window_table = True
            continue
        if not in_window_table:
            continue
        if not cells:
            break
        if _is_separator_cells(cells):
            continue
        labels.append(cells[0])
    return labels


def _audit_execution_windows(lines):
    front = _front_page_lines(lines)
    labels = set(_extract_execution_window_labels(lines))
    required_windows = (
        ZERO_POSITION_REQUIRED_EXECUTION_WINDOWS
        if _final_summary_is_zero_position(front)
        else REQUIRED_EXECUTION_WINDOWS
    )
    findings = []
    for window in required_windows:
        if window not in labels:
            findings.append(
                _finding(
                    "execution_window_missing",
                    f"front-page execution plan is missing required window: {window}",
                )
            )
    return findings


def _audit_execution_conditions(lines):
    if not _extract_execution_window_labels(lines):
        return []
    front = _front_page_lines(lines)
    front_text = "\n".join(front)
    required_conditions = list(REQUIRED_EXECUTION_CONDITIONS)
    if _final_summary_is_zero_position(front):
        required_conditions = [
            (label, markers)
            for label, markers in required_conditions
            if label not in {"失效价 / 单笔-5%底线", "固定交易窗口条件"}
        ]
    findings = []
    for label, markers in required_conditions:
        if any(marker in front_text for marker in markers):
            continue
        findings.append(
            _finding(
                "execution_condition_missing",
                f"front-page execution plan has time windows but is missing required actionable condition: {label}",
            )
        )
    return findings


def _audit_unique_action_target_contract(lines):
    findings = []
    for offset, line in enumerate(_front_page_lines(lines), 1):
        cells = _split_md_row(line)
        if len(cells) < 5 or cells[0] != "只看唯一对象":
            continue
        participation_window = cells[2]
        condition = cells[3]
        fallback = cells[4]
        is_fast_window = any(marker in participation_window for marker in ("竞价", "回封", "打板"))
        uses_structure_condition = "09:50-10:10窗口" in condition and not any(
            marker in condition for marker in ("竞价", "开盘前几分钟", "回封", "打板")
        )
        if is_fast_window and uses_structure_condition:
            findings.append(
                _finding(
                    "fast_window_polluted_by_structure_condition",
                    "fast execution windows must render auction/opening/reseal steps instead of structure-only condition",
                    line=offset,
                )
            )
        if is_fast_window and fallback != "不满足回到0%":
            findings.append(
                _finding(
                    "fast_window_fallback_not_zero",
                    "fast participation windows must fall back to 0% when the preplanned path does not trigger",
                    line=offset,
                )
            )
    return findings


def _audit_monthly_rhythm_section(lines):
    front = _front_page_lines(lines)
    findings = []
    for offset, line in enumerate(front, 1):
        cells = _split_md_row(line)
        if cells and cells[0] == "今日信号等级":
            findings.append(
                _finding(
                    "legacy_signal_grade_label",
                    "front page must use 进攻仓位三态 instead of 今日信号等级",
                    line=offset,
                )
            )
        if cells and cells[0] == "仓位攻击等级":
            findings.append(
                _finding(
                    "legacy_position_grade_label",
                    "front page must use 进攻仓位三态 instead of 仓位攻击等级",
                    line=offset,
                )
            )
    if MONTHLY_RHYTHM_HEADING not in front:
        findings.append(
            _finding(
                "monthly_rhythm_missing",
                "front page must render monthly attack/defense rhythm before stock selection",
            )
        )
        return findings
    section_text = "\n".join(_section_after(front, MONTHLY_RHYTHM_HEADING))
    section_lines = _section_after(front, MONTHLY_RHYTHM_HEADING)
    section_values = {}
    for line in section_lines:
        cells = _split_md_row(line)
        if len(cells) >= 2 and not _is_separator_cells(cells):
            section_values[cells[0]] = cells[1]
    for label in MONTHLY_RHYTHM_REQUIRED_LABELS:
        if f"| {label} |" not in section_text:
            findings.append(
                _finding(
                    "monthly_rhythm_field_missing",
                    f"monthly rhythm section is missing required field: {label}",
                )
            )
    attack_grade = section_values.get("进攻仓位三态")
    if attack_grade is not None and attack_grade not in POSITION_ATTACK_GRADE_LABELS:
        findings.append(
            _finding(
                "position_attack_grade_invalid",
                "进攻仓位三态 must be one of: 0%, 50%, 100%",
            )
        )
    max_position = _parse_percent_int(section_values.get("明日最大仓位"))
    min_position = POSITION_ATTACK_GRADE_MIN_POSITION.get(attack_grade)
    if max_position is not None and min_position is not None and min_position > max_position:
        findings.append(
            _finding(
                "position_attack_grade_exceeds_max_position",
                "进攻仓位三态 cannot require more position than 明日最大仓位 allows",
            )
        )
    return findings


def _audit_candidate_section_contract(lines):
    front = _front_page_lines(lines)
    findings = []
    for index, line in enumerate(front, 1):
        if line in LEGACY_CANDIDATE_SECTION_TITLES:
            findings.append(
                _finding(
                    "legacy_candidate_section_title",
                    f"front-page candidate section must use 个股裁决 / 备用观察 instead of legacy title: {line}",
                    line=index,
                )
            )
    if "## 五、个股解读" in front and "### 1. 个股裁决" not in front:
        findings.append(
            _finding(
                "candidate_verdict_missing",
                "front-page stock section must render 个股裁决 with 当前状态",
            )
        )
    stock_section = "\n".join(_section_after(front, "### 1. 个股裁决"))
    if stock_section and "| 当前状态 |" not in stock_section:
        findings.append(
            _finding(
                "candidate_state_missing",
                "front-page 个股裁决 must include 当前状态",
            )
        )
    return findings


def _audit_process_evidence_headings(lines):
    findings = []
    for index, line in enumerate(lines, 1):
        text = str(line or "").strip()
        if not text or "过程证据" in text:
            continue
        if not text.startswith(("#", "*")):
            continue
        if _is_front_page_sniper_derivation_heading(lines, index - 1, text):
            continue
        if any(title in text for title in PROCESS_EVIDENCE_TITLES):
            findings.append(
                _finding(
                    "process_evidence_heading_missing_marker",
                    f"过程证据标题必须标注（过程证据）: {text}",
                    line=index,
                )
            )
    return findings


def _is_front_page_sniper_derivation_heading(lines, zero_based_index, text):
    if "最终标的传导链" not in text:
        return False
    if APPENDIX_HEADING in list(lines)[:zero_based_index]:
        return False
    title = re.sub(r"^[#*\s]+|[*\s:：]+$", "", text)
    if title != "最终标的传导链":
        return False
    in_code_block = False
    code_block_lines = []
    for line in list(lines)[zero_based_index + 1 :]:
        value = str(line or "").strip()
        if value.startswith("#"):
            break
        if not value:
            continue
        if not in_code_block:
            if value == "```text":
                in_code_block = True
                continue
            if value.startswith("*"):
                break
            continue
        if value == "```":
            break
        code_block_lines.append(value)
    return bool(code_block_lines) and any((_m("最终观察", "锚") in value or "最终观察对象" in value) for value in code_block_lines)


def audit_new_stock_visibility(markdown_text):
    lines = _lines(markdown_text)
    if NEW_STOCK_VISIBILITY_HEADING not in lines:
        return {"passed": True, "findings": []}
    section_text = "\n".join(_section_after(lines, NEW_STOCK_VISIBILITY_HEADING))
    if any(marker in section_text for marker in NEW_STOCK_VISIBILITY_MARKERS):
        return {"passed": True, "findings": []}
    return {
        "passed": False,
        "findings": [
            _finding(
                "new_stock_visibility_missing",
                "新股周期判定缺少升级或不参与原因",
            )
        ],
    }


def _audit_mainline_capacity_regime_contract(lines):
    front = _front_page_lines(lines)
    findings = []
    for index, line in enumerate(front, 1):
        if str(line).strip() == LEGACY_DOUBLE_MAINLINE_HEADER:
            findings.append(
                _finding(
                    "legacy_double_mainline_table",
                    "front-page mainline section must use 主线容量与格局判断 instead of legacy double-mainline table",
                    line=index,
                )
            )
    if MAINLINE_CAPACITY_REGIME_HEADING not in front or MAINLINE_CAPACITY_REGIME_HEADER not in front:
        findings.append(
            _finding(
                "mainline_capacity_regime_missing",
                "front-page cycle section must render 主线容量与格局判断",
            )
        )
    if MAINLINE_ATTACK_EVIDENCE_HEADING not in front or MAINLINE_ATTACK_EVIDENCE_HEADER not in front:
        findings.append(
            _finding(
                "mainline_attack_evidence_missing",
                "front-page cycle section must render 主线攻击证据",
            )
        )
    return findings


def _audit_legacy_surface_wording(lines):
    report_text = "\n".join(str(line or "") for line in lines)
    findings = []
    for marker in find_legacy_surface_wording(report_text):
        for offset, line in enumerate(lines, 1):
            if marker not in str(line or ""):
                continue
            findings.append(
                _finding(
                    "legacy_surface_wording",
                    f"report must use 资格/条件/可做 wording instead of legacy marker: {marker}",
                    line=offset,
                )
            )
            break
    return findings


def _audit_legacy_trading_time_wording(lines):
    report_text = "\n".join(lines)
    findings = []
    for marker in LEGACY_TRADING_TIME_WORDING_MARKERS:
        if marker not in report_text:
            continue
        findings.append(
            _finding(
                "legacy_trading_time_wording",
                f"report uses old timing language instead of fixed trading windows: {marker}",
            )
        )
    return findings


def _strip_heading_marks(line):
    text = str(line or "").strip()
    while text.startswith("#"):
        text = text[1:].lstrip()
    return text


def _audit_appendix_duplicate_front_page_sections(lines):
    findings = []
    appendix = _appendix_lines(lines)
    appendix_start_line = len(lines) - len(appendix)
    for index, line in enumerate(appendix, 1):
        heading = _strip_heading_marks(line)
        if heading in APPENDIX_DUPLICATE_FRONT_PAGE_HEADINGS:
            findings.append(
                _finding(
                    "appendix_duplicate_front_page_section",
                    f"appendix mirrors front-page section heading: {heading}",
                    line=appendix_start_line + index,
                )
            )
    return findings


def _audit_duplicate_no_trade(lines):
    findings = []
    seen = {}
    for index, line in enumerate(lines, 1):
        text = str(line).strip()
        if not text or text.startswith("|") or text.startswith("#"):
            continue
        if not any(marker in text for marker in NO_TRADE_MARKERS):
            continue
        seen.setdefault(text, []).append(index)
    for text, indexes in seen.items():
        if len(indexes) > 1:
            findings.append(
                _finding(
                    "duplicate_no_trade_conclusion",
                    f"repeated no-trade conclusion: {text}",
                    line=indexes[1],
                )
            )
    return findings


def _normalize_table_cell(text):
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    return value


def _audit_front_page_duplicate_long_cells(lines):
    return []


def _audit_degraded_fake_zero(lines):
    findings = []
    for index, line in enumerate(lines, 1):
        text = str(line)
        if "0.00%" not in text:
            continue
        if any(marker in text for marker in DEGRADED_MARKERS):
            findings.append(
                _finding(
                    "degraded_fake_zero_percent",
                    "degraded or missing data must not render as a real 0.00%",
                    line=index,
                )
            )
    return findings


def _audit_market_breadth_incomplete(lines):
    findings = []
    for index, line in enumerate(lines, 1):
        text = str(line)
        sentence_match = re.search(r"上涨\s*0\s*家[、,，]\s*下跌\s*0\s*家", text)
        if sentence_match:
            findings.append(
                _finding(
                    "market_breadth_incomplete",
                    "涨跌家数缺失，关键数据不完整，停止生成",
                    line=index,
                )
            )
            continue
        cells = _split_md_row(line)
        if len(cells) < 2 or cells[0] != "涨跌比":
            continue
        match = re.search(r"(-?\d+(?:\.\d+)?)\s*/\s*(-?\d+(?:\.\d+)?)", cells[1])
        if not match:
            findings.append(
                _finding(
                    "market_breadth_incomplete",
                    "涨跌比缺少上涨/下跌家数，关键数据不完整，停止生成",
                    line=index,
                )
            )
            continue
        up_count = float(match.group(1))
        down_count = float(match.group(2))
        if up_count <= 0 or down_count <= 0:
            findings.append(
                _finding(
                    "market_breadth_incomplete",
                    "涨跌比缺少上涨/下跌家数，关键数据不完整，停止生成",
                    line=index,
                )
            )
    return findings


def _stock_codes_in_text(text):
    return set(re.findall(r"(?<!\d)(\d{6})(?!\d)", str(text or "")))


def _audit_position_context_contradictions(lines):
    full_text = "\n".join(str(line or "") for line in lines)
    no_holding_markers = ("无昨日持仓", "无持仓负担", "无旧仓")
    findings = []
    if "未输入持仓" in full_text and any(marker in full_text for marker in no_holding_markers):
        for index, line in enumerate(lines, 1):
            if any(marker in str(line or "") for marker in no_holding_markers):
                findings.append(
                    _finding(
                        "unknown_position_rendered_as_no_holding",
                        "未输入持仓时不能渲染成无持仓结论",
                        line=index,
                    )
                )
                break
    if "已有昨日持仓" in full_text and any(marker in full_text for marker in no_holding_markers):
        for index, line in enumerate(lines, 1):
            if any(marker in str(line or "") for marker in no_holding_markers):
                findings.append(
                    _finding(
                        "position_context_contradiction",
                        "已有昨日持仓时不能同时渲染无持仓结论",
                        line=index,
                    )
                )
                break
    return findings


def _front_account_section_with_offsets(lines):
    front = _front_page_lines(lines)
    section = []
    in_account = False
    for index, line in enumerate(front, 1):
        text = str(line or "")
        if text == "## 明日账户建议":
            in_account = True
            section.append((index, line))
            continue
        if in_account and text.startswith("## "):
            break
        if in_account:
            section.append((index, line))
    return section


def _audit_account_advice_position_contract(lines):
    section = _front_account_section_with_offsets(lines)
    if not section:
        return []

    rows = []
    for index, line in section:
        cells = _split_md_row(line)
        if len(cells) >= 2 and not _is_separator_cells(cells):
            rows.append((index, cells[0], cells[1]))

    findings = []
    labels = {label for _, label, _ in rows}
    if "明日仓位" not in labels:
        findings.append(
            _finding(
                "account_advice_missing_position",
                "明日账户建议必须写明日仓位，不能只写观察动作",
                line=section[0][0],
            )
        )

    for index, label, value in rows:
        if label != "T0主对象":
            continue
        if not str(value or "").strip() or str(value or "").strip() in {"-", "暂无"}:
            findings.append(
                _finding(
                    "t0_main_object_missing_target",
                    "T0主对象必须写清对象，不能留空",
                    line=index,
                )
            )
        break
    return findings


def _audit_incomplete_candidate_execution_plan(lines):
    incomplete_codes = set()
    findings = []
    for index, line in enumerate(lines, 1):
        text = str(line or "")
        if "关键数据不完整" not in text and "数据缺失" not in text:
            continue
        cells = _split_md_row(line)
        if "关键数据不完整" in text and "等触发条件成立" in text and len(cells) >= 9:
            findings.append(
                _finding(
                    "incomplete_candidate_waits_for_trigger",
                    "候选关键数据不完整时不能写等触发条件成立",
                    line=index,
                )
            )
        incomplete_codes.update(_stock_codes_in_text(text))
    if not incomplete_codes:
        return findings
    for index, line in enumerate(lines, 1):
        text = str(line or "")
        if "确认后执行预案" not in text:
            continue
        codes = _stock_codes_in_text(text)
        if not codes or not (codes & incomplete_codes):
            continue
        findings.append(
            _finding(
                "incomplete_candidate_has_execution_plan",
                "候选关键数据不完整时不能输出确认后执行预案",
                line=index,
            )
        )
    return findings


def _line_has_zero_position_positive_participation_language(text):
    if not any(marker in text for marker in ZERO_POSITION_POSITIVE_PARTICIPATION_MARKERS):
        return False
    return not any(marker in text for marker in ZERO_POSITION_ALLOWED_PARTICIPATION_MARKERS)


def _has_strong_zero_position_basis(text):
    text = str(text or "").strip()
    if not text:
        return False
    if any(marker in text for marker in ZERO_POSITION_WEAK_BASIS_MARKERS):
        return any(marker in text for marker in ZERO_POSITION_STRONG_BASIS_MARKERS)
    return any(marker in text for marker in ZERO_POSITION_STRONG_BASIS_MARKERS)


def _audit_zero_position_participation_language(lines):
    front = _front_page_lines(lines)
    if not _final_summary_is_zero_position(front):
        return []
    findings = []
    for index, line in enumerate(lines, 1):
        text = str(line or "")
        if not _line_has_zero_position_positive_participation_language(text):
            continue
        findings.append(
            _finding(
                "zero_position_participation_language",
                "最终0%不参与时，报告只能写观察或不新增参与，不能写正向参与口径",
                line=index,
            )
        )
    return findings


def _audit_candidate_identity_conflicts(lines):
    crossline_codes = set()
    recent_codes = set()
    for line in lines:
        text = str(line or "")
        codes = _stock_codes_in_text(text)
        if codes:
            recent_codes = codes
        if "跨线对象" in text:
            crossline_codes.update(codes or recent_codes)
    if not crossline_codes:
        return []
    findings = []
    for index, line in enumerate(lines, 1):
        cells = _split_md_row(line)
        if not cells or _is_separator_cells(cells):
            continue
        row_text = " ".join(cells)
        if "主线核心" not in row_text:
            continue
        codes = _stock_codes_in_text(row_text)
        if not codes or not (codes & crossline_codes):
            continue
        findings.append(
            _finding(
                "candidate_identity_conflict",
                "同一候选不能同时渲染为跨线对象和主线核心",
                line=index,
            )
        )
    return findings


def _audit_success_rates_match_request_logs(lines):
    has_request_issue = False
    has_full_success_rate = False
    for line in lines:
        text = str(line or "")
        cells = _split_md_row(text)
        if "成功率" in text and "(100.0%)" in text:
            has_full_success_rate = True
        if not cells or _is_separator_cells(cells):
            continue
        row_text = " ".join(cells)
        if "request." not in row_text:
            continue
        if "degraded" in row_text or "error" in row_text or "⚠️" in row_text or "❌" in row_text:
            has_request_issue = True
        elif len(cells) >= 7 and (cells[5] == "是" or cells[6] not in ("", "-")):
            has_request_issue = True
    if not (has_request_issue and has_full_success_rate):
        return []
    for index, line in enumerate(lines, 1):
        if "成功率" in str(line or "") and "(100.0%)" in str(line or ""):
            return [
                _finding(
                    "success_rate_ignores_request_issues",
                    "请求审计存在降级或异常时统计信息不能显示100%",
                    line=index,
                )
            ]
    return []


def _audit_market_fit_observation_count(lines):
    visible_pool_count = None
    for line in lines:
        text = str(line or "")
        if "明天观察池" not in text:
            continue
        match = re.search(r"明天观察池\s*\|\s*(\d+)\s*只", text)
        if match:
            visible_pool_count = int(match.group(1))
            break
    if visible_pool_count is None:
        return []
    findings = []
    for index, line in enumerate(lines, 1):
        match = re.search(r"观察池命中\s*(\d+)\s*只", str(line or ""))
        if not match:
            continue
        observation_hits = int(match.group(1))
        if observation_hits <= visible_pool_count:
            continue
        findings.append(
            _finding(
                "market_fit_observation_hits_exceed_visible_pool",
                "观察池命中数不能大于明天观察池可见数量",
                line=index,
            )
        )
    return findings


def _extract_table_rows_after_header(lines, header_line):
    rows = []
    try:
        start = list(lines).index(header_line)
    except ValueError:
        return rows
    for line in list(lines)[start + 1 :]:
        cells = _split_md_row(line)
        if not cells:
            break
        if _is_separator_cells(cells):
            continue
        rows.append(cells)
    return rows


def _extract_all_table_rows_after_header(lines, header_line):
    source_lines = list(lines)
    tables = []
    for start, line in enumerate(source_lines):
        if line != header_line:
            continue
        rows = []
        for row_line in source_lines[start + 1 :]:
            cells = _split_md_row(row_line)
            if not cells:
                break
            if _is_separator_cells(cells):
                continue
            rows.append(cells)
        tables.append({"start": start, "rows": rows})
    return tables


def _has_recent_mainline_turnover_summary_near(lines, table_start):
    start = max(0, int(table_start or 0) - 4)
    nearby_text = "\n".join(list(lines)[start : int(table_start or 0)])
    return (
        "近25个交易日主线成交额占比趋势" in nearby_text
        or "主线切换成交额记录" in nearby_text
        or "小周期成交额与主线切换判断" in nearby_text
    )


def _has_real_mainline_turnover_value(value):
    text = str(value or "").strip()
    if not text or text in {"-", "待累计", "数据暂缺"}:
        return False
    return bool(re.search(r"\d", text))


def _mainline_turnover_row_has_unconfirmed_label_with_real_amount(cells):
    if len(cells) < 7:
        return False
    small_cycle_line = str(cells[1] or "").strip()
    has_unconfirmed_label = small_cycle_line in {"暂无确认主线", "暂无确认主攻线", "小周期待确认"}
    if not has_unconfirmed_label:
        return False
    return _has_real_mainline_turnover_value(cells[2]) or _has_real_mainline_turnover_value(cells[4])


def _audit_market_base_freshness(lines):
    target_date = _report_target_date(lines)
    if not target_date:
        return []
    front = _front_page_lines(lines)
    findings = []
    top50_rows = _extract_table_rows_after_header(front, TOP50_TURNOVER_HEADER)
    if top50_rows:
        row_dates = [cells[0] for cells in top50_rows if cells and re.match(r"\d{4}-\d{2}-\d{2}$", cells[0])]
        if row_dates and target_date not in row_dates:
            findings.append(
                _finding(
                    "top50_target_date_missing",
                    f"Top50成交额占比趋势 must include report date {target_date}, got {row_dates[0]} to {row_dates[-1]}",
                )
            )
        if len(row_dates) < 25:
            findings.append(
                _finding(
                    "top50_recent_window_incomplete",
                    f"Top50成交额占比趋势 must render recent 25 trading rows, got {len(row_dates)}",
                )
            )

    mainline_tables = _extract_all_table_rows_after_header(lines, MAINLINE_TURNOVER_HEADER)
    if mainline_tables and target_date >= "2026-05-20":
        for table in mainline_tables:
            mainline_rows = table["rows"]
            row_dates = [cells[0] for cells in mainline_rows if cells and re.match(r"\d{4}-\d{2}-\d{2}$", cells[0])]
            if not row_dates:
                continue
            table_line = table["start"] + 1
            if target_date not in row_dates:
                findings.append(
                    _finding(
                        "mainline_turnover_target_date_missing",
                        f"主线成交额占比趋势必须包含报告日期 {target_date}，当前日期范围是 {row_dates[0]} 到 {row_dates[-1]}",
                        line=table_line,
                    )
                )
            if len(row_dates) < 25:
                findings.append(
                    _finding(
                        "mainline_turnover_recent_window_incomplete",
                        f"主线成交额占比趋势必须渲染近25个交易日，当前只有 {len(row_dates)} 行",
                        line=table_line,
                    )
                )
            if not _has_recent_mainline_turnover_summary_near(lines, table["start"]):
                findings.append(
                    _finding(
                        "mainline_turnover_trend_summary_missing",
                        "主线成交额占比趋势必须给出近25个交易日解读",
                        line=table_line,
                    )
                )
            for offset, cells in enumerate(mainline_rows, start=table_line + 2):
                if _mainline_turnover_row_has_unconfirmed_label_with_real_amount(cells):
                    findings.append(
                        _finding(
                            "mainline_turnover_unconfirmed_label_with_real_amount",
                            "主线成交额占比趋势不能把已有成交额或占比的历史行标成暂无确认主线",
                            line=offset,
                        )
                    )

    new_high_section = _section_after(front, NEW_HIGH_FEEDBACK_HEADING)
    if new_high_section:
        section_text = "\n".join(new_high_section)
        if "最近可用因子日" in section_text:
            findings.append(
                _finding(
                    "new_high_previous_factor_date_substitute",
                    "创新高趋势反馈 must not substitute a previous factor date for the report date",
                )
            )
        has_target_row = any(str(line).startswith(f"| {target_date} |") for line in new_high_section)
        if not has_target_row:
            findings.append(
                _finding(
                    "new_high_target_date_missing",
                    f"创新高趋势反馈 must include report date row: {target_date}",
                )
            )

    price_band_section = _section_after(front, PRICE_BAND_STYLE_HEADING)
    price_band_rows = _extract_table_rows_after_header(front, PRICE_BAND_STYLE_HEADER)
    if price_band_section or price_band_rows:
        row_dates = [cells[0] for cells in price_band_rows if cells and re.match(r"\d{4}-\d{2}-\d{2}$", cells[0])]
        latest_row_date = max(row_dates) if row_dates else ""
        summary_match = re.search(r"最近可用窗口（截至(\d{4}-\d{2}-\d{2})）", "\n".join(price_band_section))
        summary_latest_date = summary_match.group(1) if summary_match else ""
        latest_evidence_date = max([date for date in (latest_row_date, summary_latest_date) if date], default="")
        gap_days = _date_gap_days(target_date, latest_evidence_date) if latest_evidence_date else None
        is_not_near_target = gap_days is None or gap_days > 3
        if row_dates and target_date not in row_dates and is_not_near_target:
            findings.append(
                _finding(
                    "price_band_style_target_date_missing",
                    f"价格带风格趋势必须覆盖报告日期附近交易日 {target_date}，当前日期范围是 {min(row_dates)} 到 {max(row_dates)}",
                )
            )
        summary_gap_days = _date_gap_days(target_date, summary_latest_date) if summary_latest_date else None
        if summary_gap_days is not None and summary_gap_days > 3:
            findings.append(
                _finding(
                    "price_band_style_recent_window_stale",
                    f"价格带风格趋势截至 {summary_latest_date}，不能支撑 {target_date} 的市场判断",
                )
            )
    return findings


def _audit_market_base_readability(lines):
    front = _front_page_lines(lines)
    findings = []
    for index, line in enumerate(front, 1):
        if str(line).strip() == MARKET_STATUS_HEADING:
            next_line = str(front[index]).strip() if index < len(front) else ""
            if next_line.startswith("| 市场贴合度 |"):
                findings.append(
                    _finding(
                        "market_fit_row_outside_status_table",
                        "市场贴合度必须进入市场状态结论表格，不能单独插在标题下面",
                        line=index + 1,
                    )
                )
    if MARKET_STATUS_HEADING in front:
        section = _section_after(front, MARKET_STATUS_HEADING)
        if MARKET_STATUS_HEADER not in section:
            findings.append(
                _finding(
                    "market_status_table_basis_missing",
                    "市场状态结论必须使用 项目/结论/依据 三列表格",
                )
            )
        section_text = "\n".join(section)
        if "| 融资承接压力 | 待累计 |" in section_text and MARGIN_PRESSURE_APPENDIX_HEADER in lines:
            findings.append(
                _finding(
                    "market_status_margin_pressure_stale",
                    "融资承接附录已有结构化数据时，市场状态结论不能继续写待累计",
                )
            )
    if MARGIN_PRESSURE_FRONT_HEADER in front:
        rows = _extract_table_rows_after_header(front, MARGIN_PRESSURE_FRONT_HEADER)
        dated_rows = [cells for cells in rows if cells and re.match(r"\d{4}-\d{2}-\d{2}$", cells[0])]
        if len(dated_rows) < 10:
            findings.append(
                _finding(
                    "margin_pressure_recent_window_incomplete",
                    f"首页融资承接表必须展示近10日，当前只有 {len(dated_rows)} 行",
                )
            )
    if MARGIN_PRESSURE_APPENDIX_HEADER in lines:
        rows = _extract_table_rows_after_header(lines, MARGIN_PRESSURE_APPENDIX_HEADER)
        dated_rows = [cells for cells in rows if cells and re.match(r"\d{4}-\d{2}-\d{2}$", cells[0])]
        if len(dated_rows) < 25:
            findings.append(
                _finding(
                    "margin_pressure_appendix_window_incomplete",
                    f"附录融资承接表必须展示完整25日，当前只有 {len(dated_rows)} 行",
                )
            )
    return findings


def _audit_extreme_conviction_tracking(lines):
    text = "\n".join(lines)
    if EXTREME_CONVICTION_TRACKING_HEADING not in text or EXTREME_CONVICTION_TRACKING_HEADER not in lines:
        return [
            _finding(
                "extreme_conviction_tracking_missing",
                "report must render 明日极度看好近25日跟踪表 from structured ledger data",
            )
        ]
    findings = []
    rows = _extract_table_rows_after_header(lines, EXTREME_CONVICTION_TRACKING_HEADER)
    if not rows:
        findings.append(
            _finding(
                "extreme_conviction_tracking_empty",
                "明日极度看好近25日跟踪表 must include at least one structured sample row",
            )
        )
        return findings
    elimination_markers = ("A杀淘汰", "A杀冷却", "A杀出清", "禁买", "a_kill", "a-kill")
    for row in rows:
        row_text = " ".join(row)
        row_text_lower = row_text.lower()
        if any(marker in row_text for marker in elimination_markers[:4]) or any(
            marker in row_text_lower for marker in elimination_markers[4:]
        ):
            findings.append(
                _finding(
                    "extreme_conviction_tracking_contains_a_kill",
                    "明日极度看好近25日跟踪表必须排除A杀样本",
                )
            )
            break
        if "若已买入" in row_text:
            findings.append(
                _finding(
                    "extreme_conviction_tracking_action_wording_not_historical",
                    "明日极度看好近25日跟踪表必须使用历史复盘口径，不能写成明日动作",
                )
            )
            break
    return findings


def _audit_reasoning_surface(lines):
    findings = []
    front = _front_page_lines(lines)
    front_text = "\n".join(front)
    front_text_lower = front_text.lower()
    for marker in REASONING_CHAIN_LEAK_MARKERS:
        if marker.lower() in front_text_lower:
            findings.append(
                _finding(
                    "reasoning_chain_leakage",
                    f"front page must not expose reasoning chain marker: {marker}",
                )
            )
    if REASONING_SURFACE_HEADING not in front:
        return findings
    section_text = "\n".join(_section_after(front, REASONING_SURFACE_HEADING))
    missing = [label for label in REASONING_REQUIRED_LABELS if f"| {label} |" not in section_text]
    if missing:
        findings.append(
            _finding(
                "reasoning_surface_incomplete",
                "reasoning surface is missing required rows: " + ", ".join(missing),
            )
        )
    return findings


def _audit_anti_noise_language(lines):
    findings = []
    front = _front_page_lines(lines)
    for index, line in enumerate(front, 1):
        text = str(line)
        simulation_codes_on_line = set()
        theory_codes_on_line = set()

        def append_simulation_finding(message):
            code = "simulation_noise_language"
            if code in simulation_codes_on_line:
                return
            simulation_codes_on_line.add(code)
            findings.append(_finding(code, message, line=index))

        def append_theory_finding(code, message):
            if code in theory_codes_on_line:
                return
            theory_codes_on_line.add(code)
            findings.append(_finding(code, message, line=index))

        for marker in SIMULATION_NOISE_MARKERS:
            if marker in text:
                append_simulation_finding(
                    f"front page must not use simulation/noise phrase: {marker}",
                )
        theory_action_found = False
        for marker in THEORY_ACTION_MARKERS:
            if marker in text:
                theory_action_found = True
                append_theory_finding(
                    "theory_driven_action_language",
                    f"front page must not use theory language as an action reason: {marker}",
                )
        if not theory_action_found and _has_theory_action_context(text):
            append_theory_finding(
                "theory_driven_action_language",
                "front page must not use theory concept language to justify action, qualification, or position changes",
            )
        for marker in THEORY_NOISE_MARKERS:
            if marker in text:
                append_theory_finding(
                    "theory_noise_language",
                    f"front page must not use theory/noise phrase: {marker}",
                )
        for term in THEORY_CONCEPT_TERMS:
            if term in text:
                append_theory_finding(
                    "theory_noise_language",
                    f"front page must not use unfieldized theory concept: {term}",
                )
    return findings


def _has_theory_action_context(text):
    return any(term in text for term in THEORY_CONCEPT_TERMS) and any(
        marker in text for marker in THEORY_ACTION_CONTEXT_MARKERS
    )


def _audit_legacy_daily_report_terms(lines):
    findings = []
    markers = LEGACY_OBSERVATION_SURFACE_MARKERS + LEGACY_POSITION_STYLE_MARKERS
    for offset, line in enumerate(lines, 1):
        text = str(line or "")
        matched = False
        for marker in markers:
            if marker not in text:
                continue
            findings.append(
                _finding(
                    "legacy_daily_report_term",
                    "report uses retired daily-report wording",
                    line=offset,
                )
            )
            matched = True
            break
        if matched:
            continue
    return findings


def _extract_execution_unique_target(lines):
    for line in lines:
        cells = _split_md_row(line)
        if len(cells) >= 4 and cells[0] == "只看唯一对象":
            return cells[1]
        if len(cells) >= 5 and cells[0] == "只看明日执行对象":
            return cells[1]
        if len(cells) >= 5 and cells[0] == _m("只看观察", "锚"):
            return cells[1]
        if len(cells) >= 5 and cells[0] == "只看观察对象":
            return cells[1]
        if len(cells) >= 5 and cells[0] == "只看条件观察对象":
            return cells[1]
    return ""


def _extract_closing_action_target(lines):
    in_checklist = False
    for line in lines:
        text = str(line or "")
        if text.strip() == "### 明日行动清单":
            in_checklist = True
            continue
        if in_checklist and text.startswith("#"):
            break
        if not in_checklist:
            continue
        cells = _split_md_row(text)
        if len(cells) >= 2 and cells[0] == "最终对象":
            return cells[1]
    return ""


def _extract_opening_verdict_final_object(lines):
    in_opening = False
    for line in lines:
        text = str(line or "")
        if text.strip() == "## 日报裁决总览":
            in_opening = True
            continue
        if in_opening and text.startswith("## "):
            break
        if not in_opening:
            continue
        cells = _split_md_row(text)
        if len(cells) >= 2 and cells[0] == "最终对象":
            return cells[1]
    return ""


def _extract_final_solution_result(lines):
    in_solution = False
    for line in lines:
        text = str(line or "")
        if text.strip() == "## 最终标的解题过程":
            in_solution = True
            continue
        if in_solution and text.startswith("## "):
            break
        if not in_solution:
            continue
        cells = _split_md_row(text)
        if len(cells) >= 2 and cells[0] == "最终结果":
            return cells[1]
    return ""


def _extract_final_unique_target(lines):
    for index, line in enumerate(lines):
        header = _split_md_row(line)
        target_headers = ("唯一重点对象", "重点对象")
        target_header = next((item for item in target_headers if item in header), "")
        if not target_header:
            continue
        target_index = header.index(target_header)
        for candidate in lines[index + 1 :]:
            cells = _split_md_row(candidate)
            if not cells:
                continue
            if _is_separator_cells(cells):
                continue
            if len(cells) > target_index:
                return cells[target_index]
    return ""


def _extract_final_execution_style(lines):
    for index, line in enumerate(lines):
        header = _split_md_row(line)
        if "明日执行风格" not in header:
            continue
        style_index = header.index("明日执行风格")
        for candidate in lines[index + 1 :]:
            cells = _split_md_row(candidate)
            if not cells:
                continue
            if _is_separator_cells(cells):
                continue
            if len(cells) > style_index:
                return cells[style_index]
    return ""


def _final_summary_is_zero_position(lines):
    style = _extract_final_execution_style(lines)
    target = _extract_final_unique_target(lines)
    if "0%不参与" in style:
        return True
    for line in lines:
        cells = _split_md_row(line)
        if not cells or _is_separator_cells(cells):
            continue
        if any("0%不参与" in cell for cell in cells) and _is_empty_target(target):
            return True
    return False


def _is_stopped_report_notice(markdown):
    text = str(markdown or "")
    return all(marker in text for marker in STOPPED_REPORT_REQUIRED_MARKERS)


def _audit_stopped_report_notice(markdown):
    if not _is_stopped_report_notice(markdown):
        return None
    findings = []
    for marker in STOPPED_REPORT_TRADE_PLAN_MARKERS:
        if marker not in str(markdown or ""):
            continue
        findings.append(
            _finding(
                "stopped_report_contains_trade_plan",
                "关键数据不完整的停止说明不能同时包含交易计划内容",
            )
        )
        break
    return findings


def _final_summary_has_conditional_zero_plan(lines):
    style = _extract_final_execution_style(lines)
    target = _extract_final_unique_target(lines)
    if "0%不参与" not in style:
        return False
    text = "\n".join(str(line or "") for line in list(lines or []))
    has_observation_prefix = any(marker in str(target or "") for marker in ("条件观察：", _m("观察", "锚："), "观察对象："))
    has_participation_plan = any(marker in text for marker in (_m("条件", "50%"), "50%条件执行", "才评估50%条件执行"))
    return has_observation_prefix and has_participation_plan


def _positive_participation_pct(lines):
    text = "\n".join(str(line or "") for line in list(lines or []))
    if any(marker in text for marker in ("100%核心进攻", "100%核心进攻", "条件100%核心进攻")):
        return 100
    if any(marker in text for marker in ("50%条件执行", _m("条件", "50%", "预演"))):
        return 50
    return 0


def _extract_opportunity_comparison_rows(lines):
    rows = []
    in_section = False
    for offset, line in enumerate(_front_page_lines(lines), 1):
        text = str(line or "").strip()
        if text == OPPORTUNITY_COMPARISON_HEADING:
            in_section = True
            continue
        if not in_section:
            continue
        if text.startswith("#"):
            break
        cells = _split_md_row(line)
        if not cells or _is_separator_cells(cells) or cells[0] == "对象":
            continue
        rows.append((offset, cells))
    return rows


def _is_old_position_comparison_row(cells):
    if len(cells) < 2:
        return False
    role = str(cells[1] or "")
    return any(marker in role for marker in OLD_POSITION_COMPARISON_ROLE_MARKERS)


def _is_incomplete_opportunity_cell(value):
    text = str(value or "").strip()
    if text in INCOMPLETE_OPPORTUNITY_RISK_MARKERS:
        return True
    return any(marker and marker in text for marker in INCOMPLETE_OPPORTUNITY_RISK_MARKERS if marker not in ("", "-"))


def _target_opportunity_row_has_incomplete_risk(cells):
    if len(cells) < 10:
        return True
    required_price_columns = (2, 3, 4, 6, 7)
    if any(_is_incomplete_opportunity_cell(cells[index]) for index in required_price_columns):
        return True
    risk_reward_state = str(cells[8] or "").strip()
    if risk_reward_state in ("合格", "正盈亏比"):
        return False
    if any(marker in risk_reward_state for marker in ("待计算", "不合格", "缺失", "待补")):
        return True
    return not risk_reward_state


def _audit_opportunity_comparison_contract(lines):
    front = _front_page_lines(lines)
    if _positive_participation_pct(front) < 50:
        return []
    front_text = "\n".join(str(line or "") for line in front)
    requires_comparison = any(marker in front_text for marker in ("先处理旧仓", "释放旧仓资金", "旧仓资金"))
    rows = _extract_opportunity_comparison_rows(lines)
    findings = []
    if requires_comparison and not rows:
        findings.append(
            _finding(
                "opportunity_comparison_missing",
                "50/100结论涉及旧仓资金切换时，必须先展示旧仓与新机会的风险价格对比",
            )
        )
        return findings
    for offset, cells in rows:
        if _is_old_position_comparison_row(cells):
            continue
        role_text = str(cells[1] or "").strip() if len(cells) >= 2 else ""
        action_text = str(cells[9] or "").strip() if len(cells) >= 10 else ""
        if (
            any(marker in role_text for marker in ("待识别", "观察"))
            and all(marker not in action_text for marker in ("50%", "100%", "条件执行"))
        ):
            continue
        if all(marker not in action_text for marker in ("50%", "100%", "条件执行")) and any(
            marker in action_text
            for marker in ("只保留观察", "等待盈亏比", "等待回踩", "风险价格补齐", "观察")
        ):
            continue
        if not _target_opportunity_row_has_incomplete_risk(cells):
            continue
        findings.append(
            _finding(
                "opportunity_comparison_incomplete_risk",
                "50/100结论不能同时保留风险价格或盈亏比未补齐的新目标",
                line=offset,
            )
        )
    return findings


def _is_zero_position_conflict_line(cells):
    row_text = " ".join(cells)
    if any(marker in row_text for marker in ("不新增参与", "不能转成新增参与", "暂无新增参与资格")):
        return False
    if not _has_stock_reference(cells):
        return False
    if len(cells) >= 2 and cells[0] in ZERO_POSITION_CURRENT_DECISION_ACTION_LABELS and not _is_empty_target(cells[1]):
        return True
    return any(marker in row_text for marker in ZERO_POSITION_ACTION_MARKERS)


def _audit_zero_position_tomorrow_action_consistency(lines):
    front = _front_page_lines(lines)
    if not _final_summary_is_zero_position(front):
        return []
    has_conditional_zero_plan = _final_summary_has_conditional_zero_plan(front)
    findings = []
    for offset, line in enumerate(front, 1):
        cells = _split_md_row(line)
        if not cells or _is_separator_cells(cells):
            continue
        if not _is_zero_position_conflict_line(cells):
            continue
        findings.append(
            _finding(
                "zero_position_tomorrow_action_conflict",
                "final summary is 0%不参与, but a front-page tomorrow action still names a concrete participation target",
                line=offset,
            )
        )
    if not has_conditional_zero_plan:
        for offset, line in enumerate(lines, 1):
            cells = _split_md_row(line)
            if not cells or _is_separator_cells(cells):
                continue
            if len(cells) < 2 or cells[0] not in ZERO_POSITION_CURRENT_DECISION_ACTION_LABELS:
                continue
            if _is_empty_target(cells[1]):
                continue
            findings.append(
                _finding(
                    "zero_position_tomorrow_action_conflict",
                    "final summary is 0%不参与, but a current decision panel still names a main or backup participation object",
                    line=offset,
                )
            )
        for offset, line in enumerate(lines, 1):
            text = str(line or "")
            if not any(marker in text for marker in ZERO_POSITION_LEGACY_TOMORROW_WORDING_MARKERS):
                continue
            findings.append(
                _finding(
                    "zero_position_legacy_tomorrow_wording",
                    "final summary is 0%不参与, but report still contains old tomorrow-action wording",
                    line=offset,
                )
            )
    return findings


def _audit_chanlun_tomorrow_decision_consistency(lines, companion_html):
    if companion_html is None:
        return []
    elimination_findings = _audit_elimination_tournament_consistency(lines, companion_html)
    if elimination_findings is not None:
        return elimination_findings
    preflight_findings = _audit_sector_capital_preflight_consistency(lines, companion_html)
    if preflight_findings is not None:
        return preflight_findings
    front = _front_page_lines(lines)
    if not _final_summary_is_zero_position(front):
        return []
    values = _extract_chanlun_tomorrow_decision_values(companion_html)
    if values is None:
        return [
            _finding(
                "chanlun_tomorrow_decision_missing",
                "final summary is 0%不参与, but companion HTML is missing 明日抉择",
            )
        ]
    max_position = _parse_percent_int(values.get("明日最大仓位"))
    participation = values.get("新增参与", "")
    final_action = values.get("最终执行条件", "")
    if (
        max_position == 0
        and "不参与" in participation
        and any(marker in final_action for marker in CHANLUN_ZERO_POSITION_ACTION_MARKERS)
    ):
        return []
    return [
        _finding(
            "chanlun_tomorrow_decision_conflict",
            "final summary is 0%不参与, but companion HTML 明日抉择 does not match 0%不参与",
        )
    ]


def _audit_position_state_rendering(lines):
    front = _front_page_lines(lines)
    style = _extract_final_execution_style(front)
    if not style:
        return []
    if any(marker in style for marker in LEGACY_POSITION_STYLE_MARKERS):
        return [
            _finding(
                "legacy_position_style",
                "final summary must render 0/50/100 position state instead of legacy empty/short/30% style",
            )
        ]
    if not any(marker in style for marker in POSITION_STYLE_GRADE_MARKERS):
        return [
            _finding(
                "position_style_missing_grade",
                "final summary execution style must include 0/50/100 position state",
            )
        ]
    return []


def _audit_next_day_attribution_contract(lines):
    section = _section_after(lines, "## 次日归因闭环")
    if not section:
        return []
    findings = []
    for offset, line in enumerate(lines, 1):
        cells = _split_md_row(line)
        if len(cells) < 4 or _is_separator_cells(cells):
            continue
        row_text = " ".join(cells)
        bucket = cells[3]
        if "过程候选" in row_text and bucket in {"execution_hit", "final_observation_hit"}:
            findings.append(
                _finding(
                    "next_day_attribution_process_counted_as_final",
                    "过程候选不能计入最终或执行命中",
                    line=offset,
                )
            )
        if "历史" in row_text and bucket in {"execution_hit", "final_observation_hit", "process_candidate_hit"}:
            findings.append(
                _finding(
                    "next_day_attribution_history_counted_as_current",
                    "历史证据不能计入当前最终对象命中",
                    line=offset,
                )
            )
    report_text = "\n".join(str(line or "") for line in lines)
    if "报告没有明日执行对象" in report_text and re.search(r"\|\s*[^|]+\|\s*[^|]+\|\s*[^|]+\|\s*execution_hit\s*\|", report_text):
        findings.append(
            _finding(
                "next_day_attribution_execution_hit_without_plan",
                "0%或仅观察报告不能计入执行命中",
            )
        )
    return findings


def _target_text_without_role(value):
    text = str(value or "").strip()
    return re.sub(rf"^(?:条件观察|{_m('观察', '锚')}|观察对象|条件执行对象|明日执行对象|最终执行对象|执行对象|执行目标)[:：]\s*", "", text).strip()


def _is_empty_target(value):
    text = _target_text_without_role(value)
    if text in (
        "",
        "-",
        "无",
        "暂无",
        "待补事实",
        "不做",
        "无明日执行对象",
        "无执行对象",
        "无执行目标",
        "无当前对象",
    ):
        return True
    if re.search(r"(?<!\d)\d{6}(?!\d)", text):
        return False
    return (
        "暂无" in text
        or "不做" in text
        or "无明日执行对象" in text
        or "无执行对象" in text
        or "无执行目标" in text
        or "无当前对象" in text
        or "当前最终对象为空" in text
    )


def _is_empty_execution_target(value):
    text = str(value or "").strip()
    return text in ("", "-", "无", "暂无", "不做") or _is_empty_target(text)


def _extract_front_kv_value(front_lines, label):
    for offset, line in enumerate(front_lines, 1):
        cells = _split_md_row(line)
        if len(cells) >= 2 and cells[0] == label:
            return cells[1], offset
    return "", None


def _audit_zero_position_decision_attribution(lines):
    front = _front_page_lines(lines)
    if not _final_summary_is_zero_position(front):
        return []
    front_execution_object = _extract_front_execution_object(lines)
    front_text = "\n".join(str(line or "") for line in front)
    if (
        front_execution_object
        and _target_identity(front_execution_object)
        and "## 50%条件执行条件" in front_text
        and "条件满足才50%条件执行" in front_text
    ):
        return []

    required_labels = ("明日仓位", "执行目标", "不参与依据", "无执行目标原因", "责任归因")
    values = {}
    offsets = {}
    for label in required_labels:
        value, offset = _extract_front_kv_value(front, label)
        values[label] = str(value or "").strip()
        offsets[label] = offset

    missing = [label for label in required_labels if not values[label]]
    findings = []
    if missing or "0%不参与" not in values["明日仓位"]:
        findings.append(
            _finding(
                "zero_position_decision_attribution_missing",
                "0%不参与必须写明日仓位、执行目标、不参与依据、无执行目标原因和责任归因",
                line=offsets.get("明日仓位"),
            )
        )

    execution_target = values["执行目标"]
    if execution_target and not _is_empty_execution_target(execution_target):
        findings.append(
            _finding(
                "zero_position_execution_target_conflict",
                "0%不参与时执行目标必须写无，具体对象只能写观察对象",
                line=offsets.get("执行目标"),
            )
        )

    attribution = values["责任归因"]
    if attribution and attribution not in ("市场问题", "决策问题", "数据问题", "账户问题"):
        findings.append(
            _finding(
                "zero_position_decision_attribution_missing",
                "0%不参与的责任归因必须区分市场问题、决策问题、数据问题或账户问题",
                line=offsets.get("责任归因"),
            )
        )

    observation_anchor, anchor_offset = _extract_front_kv_value(front, "观察对象")
    if not observation_anchor:
        observation_anchor, anchor_offset = _extract_front_kv_value(front, _m("观察", "锚"))
    if observation_anchor and not _is_empty_target(observation_anchor):
        basis = values["不参与依据"]
        if not _has_strong_zero_position_basis(basis):
            findings.append(
                _finding(
                    "zero_position_strong_basis_missing",
                    "0%不参与仍保留观察对象时，必须写清弱市场、冰点、趋势失效、关键数据不完整、账户限制或旧仓处理等强理由",
                    line=offsets.get("不参与依据") or anchor_offset,
                )
            )
        lifecycle_label_groups = (
            ("观察对象性质", _m("观察", "锚性质")),
            ("恢复评估条件",),
            ("观察对象去留", _m("观察", "锚去留")),
        )
        missing_lifecycle = [
            labels[0]
            for labels in lifecycle_label_groups
            if not any(str(_extract_front_kv_value(front, label)[0] or "").strip() for label in labels)
        ]
        if missing_lifecycle:
            findings.append(
                _finding(
                    "zero_position_observation_anchor_lifecycle_missing",
                    "0%不参与仍保留观察对象时，必须写观察对象性质、恢复评估条件和观察对象去留",
                    line=anchor_offset,
                )
            )

    return findings


def _target_identity(value):
    text = _target_text_without_role(value)
    if _is_empty_target(text):
        return ""
    match = re.search(r"(?<!\d)(\d{6})(?!\d)", text)
    if match:
        return match.group(1)
    return text


def _report_final_object_sources(lines):
    front = _front_page_lines(lines)
    appendix = _appendix_lines(lines)
    sources = []

    for label, value in (
        ("opening_verdict", _extract_opening_verdict_final_object(front)),
        ("final_solution", _extract_final_solution_result(front)),
        ("opening_execution", _extract_front_execution_object(lines)),
        ("execution_plan", _extract_execution_unique_target(front)),
        ("final_object", _extract_final_unique_target(front)),
        ("next_day_action", _extract_closing_action_target(front)),
    ):
        identity = _target_identity(value)
        if identity:
            sources.append((label, identity, value))

    for identity in _extract_sniper_derivation_final_identities(front):
        sources.append(("process_graph", identity, identity))
    for identity in _extract_sniper_derivation_final_identities(appendix):
        sources.append(("process_graph", identity, identity))
    return sources


def _extract_front_execution_object(lines):
    for line in _front_page_lines(lines):
        cells = _split_md_row(line)
        if len(cells) >= 2 and cells[0] == "明日执行对象":
            return cells[1]
    return ""


def _extract_audit_layer_execution_object(lines):
    in_audit_layer = False
    for line in lines:
        text = str(line or "")
        if text.strip() == "## 推导审计层":
            in_audit_layer = True
            continue
        if in_audit_layer and text.startswith("## "):
            break
        if not in_audit_layer:
            continue
        if "条件执行对象：" in text:
            return text.split("条件执行对象：", 1)[-1].strip()
    return ""


def _audit_two_layer_execution_object_consistency(lines):
    front_object = _extract_front_execution_object(lines)
    if not front_object:
        return []
    audit_object = _extract_audit_layer_execution_object(lines)
    if not audit_object:
        return []
    front_identity = _target_identity(front_object)
    audit_identity = _target_identity(audit_object)
    if front_identity and audit_identity and front_identity != audit_identity:
        return [
            _finding(
                "two_layer_execution_object_mismatch",
                f"front execution object {front_object} conflicts with audit-layer object {audit_object}",
            )
        ]
    return []


def _audit_b_level_conditions(lines):
    front_text = "\n".join(str(line or "") for line in _front_page_lines(lines))
    if "## 50%条件执行条件" not in front_text:
        has_execution_conclusion = "## 明日执行结论" in front_text and "| 明日执行对象 |" in front_text
        execution_object_is_none = "| 明日执行对象 | 无 |" in front_text
        if not (has_execution_conclusion and not execution_object_is_none and "50%条件执行" in front_text):
            return []
    if "低开承接型" in front_text and "主动进攻型" in front_text:
        return []
    return [
        _finding(
            "b_level_conditions_missing",
            "front page mentions 50%条件执行 but does not render both 50%执行 trigger conditions",
        )
    ]


def _audit_front_execution_object_negation(lines):
    front_object = _extract_front_execution_object(lines)
    if not front_object or not _target_identity(front_object):
        return []
    findings = []
    negation_markers = ("不是执行对象", "不能定义明日执行对象", "不涉及明日执行对象")
    for offset, line in enumerate(_front_page_lines(lines), 1):
        text = str(line or "")
        if not any(marker in text for marker in negation_markers):
            continue
        findings.append(
            _finding(
                "front_execution_object_negated",
                "front page declares 明日执行对象 but later negates that execution object",
                line=offset,
            )
        )
    return findings


def _audit_front_execution_object_downgrade(lines):
    front_object = _extract_front_execution_object(lines)
    front_identity = _target_identity(front_object)
    if not front_identity or _is_empty_target(front_object):
        return []
    downgrade_markers = (
        _m("最终观察", "锚"),
        _m("身份=观察", "锚"),
        _m("只看观察", "锚"),
        _m("观察", "锚："),
        "0%只观察",
        "只观察",
        "不是执行目标",
        "不是执行对象",
        "不能转成新增参与",
        "缺少可执行对象",
    )
    findings = []
    for offset, line in enumerate(lines, 1):
        text = str(line or "")
        if "明日执行对象" in text:
            continue
        if "板块锚" in text and "降级观察" in text and front_identity in text:
            continue
        if front_identity not in _target_identity(text) and front_identity not in text:
            continue
        if not any(marker in text for marker in downgrade_markers):
            continue
        findings.append(
            _finding(
                "front_execution_object_downgraded",
                "front page declares 明日执行对象 but the report later downgrades the same object to observation-only",
                line=offset,
            )
        )
    return findings


def _extract_observation_anchor_identity(lines):
    for line in lines:
        text = str(line or "")
        legacy_marker = _m("**观察优先", "锚点**")
        current_marker = "**观察优先对象**"
        if legacy_marker not in text and current_marker not in text:
            continue
        marker = legacy_marker if legacy_marker in text else current_marker
        return _target_identity(text.split(marker, 1)[-1])
    return ""


def _extract_first_watch_order_identity(lines):
    found_heading = False
    for line in lines:
        text = str(line or "")
        if "**先看顺序**" in text:
            found_heading = True
            continue
        if not found_heading:
            continue
        if "👀" not in text:
            continue
        return _target_identity(text)
    return ""


def _extract_sniper_derivation_final_identity(lines):
    identities = _extract_sniper_derivation_final_identities(lines)
    return identities[0] if identities else ""


def _extract_sniper_derivation_final_identities(lines, *, include_empty=False):
    text = "\n".join(str(line or "") for line in lines)
    identities = []
    for pattern in (
        rf"{_m('最终观察', '锚')}[:：]\s*([^\n,，]+)",
        r"最终观察对象[:：]\s*([^\n,，]+)",
        r"最终对象[:：]\s*([^\n,，|]+)",
        rf"最终对象=([^\n]+?)\s+身份={_m('观察', '锚')}",
        r"最终对象=([^\n]+?)\s+身份=观察对象",
        r"最终对象=([^\n]+?)\s+身份=执行对象",
        r"最终执行对象[:：]\s*([^\n,，]+)",
        rf"canonical_target=([^\n]+?)\s+role={_m('观察', '锚')}",
        r"canonical_target=([^\n]+?)\s+role=观察对象",
        r"canonical_target=([^\n]+?)\s+role=执行对象",
    ):
        for match in re.finditer(pattern, text):
            raw_target = str(match.group(1) or "").strip()
            identity = _target_identity(raw_target)
            if not identity and include_empty:
                identity = _target_text_without_role(raw_target) or "暂无"
            if identity and identity not in identities:
                identities.append(identity)
    return identities


def _audit_final_object_identity_consistency(lines):
    front = _front_page_lines(lines)
    sources = _report_final_object_sources(lines)
    opening_target = _extract_opening_verdict_final_object(front)
    if opening_target and _is_empty_target(opening_target) and sources:
        later_detail = "；".join(f"{label}={value}" for label, _, value in sources)
        return [
            _finding(
                "opening_final_object_empty_conflict",
                f"opening final object is empty but later report surfaces name a final object: {later_detail}",
            )
        ]

    unique = []
    for source in sources:
        if source[1] not in [item[1] for item in unique]:
            unique.append(source)
    if len(unique) <= 1:
        return []
    detail = "；".join(f"{label}={value}" for label, _, value in unique)
    return [
        _finding(
            "final_object_identity_conflict",
            f"final object identity conflicts across report surfaces: {detail}",
        )
    ]


def _extract_current_daily_judgment_core_candidate(lines):
    for offset, line in enumerate(lines, 1):
        cells = _split_md_row(line)
        if len(cells) < 3:
            continue
        if cells[0] != "核心候选判断":
            continue
        if "下一交易日验证是否进入资金视野" not in cells[2]:
            continue
        return cells[1], offset
    return "", None


def _audit_daily_judgment_core_candidate_consistency(lines):
    candidate, offset = _extract_current_daily_judgment_core_candidate(lines)
    if not candidate or _is_empty_target(candidate):
        return []
    candidate_identity = _target_identity(candidate)
    if not candidate_identity:
        return []

    findings = []
    final_sources = _report_final_object_sources(lines)
    final_identities = []
    for _, identity, _ in final_sources:
        if identity and identity not in final_identities:
            final_identities.append(identity)
    if final_identities and candidate_identity not in final_identities:
        detail = "、".join(final_identities)
        findings.append(
            _finding(
                "daily_judgment_core_candidate_mismatch",
                f"T-006 current core candidate {candidate} conflicts with final object {detail}",
                line=offset,
            )
        )

    if _final_summary_is_zero_position(_front_page_lines(lines)):
        findings.append(
            _finding(
                "daily_judgment_core_candidate_without_execution",
                f"T-006 current core candidate {candidate} is concrete while final result has no execution object",
                line=offset,
            )
        )
    return findings


def _audit_derivation_audit_rejection_consistency(lines):
    final_sources = _report_final_object_sources(lines)
    final_identities = []
    for _, identity, _ in final_sources:
        if identity not in final_identities:
            final_identities.append(identity)
    if not final_identities:
        return []
    findings = []
    in_audit_layer = False
    for offset, line in enumerate(lines, 1):
        text = str(line or "")
        if text.strip() == "## 推导审计层":
            in_audit_layer = True
            continue
        if in_audit_layer and text.startswith("## "):
            break
        if not in_audit_layer:
            continue
        if "淘汰" not in text:
            continue
        rejected = [identity for identity in final_identities if identity in text]
        if not rejected:
            continue
        findings.append(
            _finding(
                "final_object_rejected_in_derivation_audit",
                f"final object appears in derivation rejected list: {', '.join(rejected)}",
                line=offset,
            )
        )
    return findings


def _audit_process_candidate_loss_reasons(lines):
    circular_reason_markers = (
        "最终解析未选为",
        "未选为最终",
        "原因=进入最终观察对象",
        "原因=进入最终执行对象",
    )
    findings = []
    in_graph = False
    for offset, line in enumerate(lines, 1):
        text = str(line or "")
        if "狙击手最终标的完整路径图" in text or "最终标的传导链" in text:
            in_graph = True
            continue
        if in_graph and text.startswith("## "):
            in_graph = False
        if not in_graph:
            continue
        if "候选=" not in text and "过程候选 /" not in text:
            continue
        if not any(marker in text for marker in circular_reason_markers):
            continue
        findings.append(
            _finding(
                "process_candidate_loss_reason_circular",
                "process candidate replacement reason must cite same-pool dimensions, not restate that it was not selected",
                line=offset,
            )
        )
    return findings


def _audit_sniper_target_derivation_consistency(lines):
    front = _front_page_lines(lines)
    appendix = _appendix_lines(lines)
    chain_identities = _extract_sniper_derivation_final_identities(front, include_empty=True)
    for identity in _extract_sniper_derivation_final_identities(appendix, include_empty=True):
        if identity not in chain_identities:
            chain_identities.append(identity)
    if not chain_identities:
        return []
    final_target = _extract_final_unique_target(front)
    final_identity = _target_identity(final_target)
    findings = []
    if final_identity and not _is_empty_target(final_target):
        mismatched = [identity for identity in chain_identities if identity != final_identity]
        if mismatched:
            findings.append(
                _finding(
                    "sniper_target_derivation_mismatch",
                    f"front-page final observation target {final_target} conflicts with derivation chain final target {mismatched[0]}",
                )
            )
    elif len(chain_identities) > 1:
        findings.append(
            _finding(
                "sniper_target_derivation_mismatch",
                f"derivation chains contain conflicting final targets {', '.join(chain_identities)}",
            )
        )
    return findings


def _extract_selection_workflow_final_identity(lines):
    text = "\n".join(str(line or "") for line in lines or [])
    if "selection_workflow.v1" in text:
        match = re.search(
            r'"selection_workflow"\s*:\s*\{.*?"schema_version"\s*:\s*"selection_workflow\.v1".*?'
            r'"final"\s*:\s*\{.*?"execution_object"\s*:\s*\{(?P<object>.*?)\}',
            text,
            re.DOTALL,
        )
        if match:
            object_text = match.group("object")
            code_match = re.search(r'"code"\s*:\s*"(?P<code>\d{6})"', object_text)
            if code_match:
                return code_match.group("code")
            name_match = re.search(r'"name"\s*:\s*"(?P<name>[^"]+)"', object_text)
            if name_match:
                return name_match.group("name")
    workflow_headings = (
        "### 工作流链条",
        "### 主线推导链",
        "### 候选流水账",
        "### 候选生命周期证据",
    )
    if not any(heading in text for heading in workflow_headings):
        return ""
    n8_match = re.search(
        r"####\s+N8\s+仓位与执行条件(?P<body>.*?)(?:\n####\s+N9|\n###\s+候选流水账|\n###\s+候选生命周期证据|\Z)",
        text,
        re.DOTALL,
    )
    if n8_match:
        code_match = re.search(r"['\"]code['\"]\s*:\s*['\"](?P<code>\d{6})['\"]", n8_match.group("body"))
        if code_match:
            return code_match.group("code")
    in_candidate_table = False
    for line in lines:
        raw = str(line or "")
        if raw.strip() in ("### 候选流水账", "### 候选生命周期证据"):
            in_candidate_table = True
            continue
        if in_candidate_table and raw.startswith("### "):
            break
        if not in_candidate_table or "最终执行对象" not in raw:
            continue
        cells = _split_md_row(raw)
        if not cells:
            continue
        identity = _target_identity(cells[0])
        if identity:
            return identity
    return ""


def _selection_workflow_declares_empty_final(lines):
    text = "\n".join(str(line or "") for line in lines or [])
    empty_markers = (
        "FINAL[\"最终：暂无\\n仓位：0%\"]",
        "FINAL[&quot;最终：暂无\\n仓位：0%&quot;]",
        "最终：暂无\\n仓位：0%",
        "| 最终结果 | N9 / final | 无；0%不参与；0% |",
        "<td>最终结果</td><td>N9 / final</td><td>无；0%不参与；0%</td>",
    )
    return any(marker in text for marker in empty_markers)


def _audit_selection_workflow_consistency(lines):
    workflow_identity = _extract_selection_workflow_final_identity(lines)
    front = _front_page_lines(lines)
    front_execution_object = _extract_front_execution_object(lines)
    front_values = (
        _extract_opening_verdict_final_object(front),
        front_execution_object,
        _extract_execution_unique_target(front),
        _extract_final_unique_target(front),
        _extract_closing_action_target(front),
    )
    front_identities = []
    for value in front_values:
        identity = _target_identity(value)
        if identity and identity not in front_identities:
            front_identities.append(identity)
    if not workflow_identity:
        if _selection_workflow_declares_empty_final(lines) and front_identities:
            return [
                _finding(
                    "selection_workflow_mismatch",
                    f"selection_workflow final object is empty, but front page still names {front_identities[0]}",
                )
            ]
        return []
    if front_execution_object and _is_empty_target(front_execution_object):
        return [
            _finding(
                "selection_workflow_mismatch",
                f"front-page execution object is empty but selection_workflow final object is {workflow_identity}",
            )
        ]
    if not front_identities:
        return []
    if workflow_identity in front_identities:
        return []
    return [
        _finding(
            "selection_workflow_mismatch",
            f"front-page object {front_identities[0]} conflicts with selection_workflow final object {workflow_identity}",
        )
    ]


def _audit_observation_anchor_consistency(lines):
    front = _front_page_lines(lines)
    final_target = _extract_final_unique_target(front)
    final_identity = _target_identity(final_target)
    if not final_identity or _is_empty_target(final_target):
        return []
    if not any(marker in str(final_target or "") for marker in (_m("观察", "锚"), "观察对象", "条件观察")):
        return []
    findings = []
    appendix = _appendix_lines(lines)
    anchor_identity = _extract_observation_anchor_identity(appendix)
    if anchor_identity and anchor_identity != final_identity:
        findings.append(
            _finding(
                "observation_anchor_mismatch",
                f"front-page observation target {final_target} conflicts with appendix observation object {anchor_identity}",
            )
        )
    first_watch_identity = _extract_first_watch_order_identity(appendix)
    if first_watch_identity and first_watch_identity != final_identity:
        findings.append(
            _finding(
                "observation_anchor_mismatch",
                f"front-page observation target {final_target} conflicts with appendix first watch order {first_watch_identity}",
            )
        )
    return findings


def _front_declares_no_current_object(lines):
    front = _front_page_lines(lines)
    candidates = (
        _extract_opening_verdict_final_object(front),
        _extract_final_solution_result(front),
        _extract_front_execution_object(lines),
        _extract_execution_unique_target(front),
        _extract_final_unique_target(front),
        _extract_closing_action_target(front),
    )
    seen_any_surface = False
    for value in candidates:
        if not str(value or "").strip():
            continue
        seen_any_surface = True
        if not _is_empty_target(value):
            return False
    return seen_any_surface


def _line_names_current_object_when_front_empty(text):
    stripped = str(text or "").strip()
    process_markers = ("过程候选", "过程样本", "回看样本", "过程证据", "非当前对象", "只回放")
    cells = _split_md_row(stripped)
    if cells:
        current_object_labels = {
            "今日关注标的",
            "明天观察池",
            "PK决胜局（期望值模型）",
            "当前执行对象",
            "主买对象",
            "补位对象",
            "主观察对象",
            "观察对象",
            "明日执行对象",
        }
        if len(cells) >= 2 and cells[0] in current_object_labels:
            value_text = " ".join(cells[1:])
            if any(marker in value_text for marker in process_markers) or _is_empty_target(value_text):
                return ""
            if _target_identity(value_text):
                return cells[0]
        if "明天具体怎么做" in cells and "股票" in cells:
            return ""
        if len(cells) >= 3 and any("确认后执行预案" in cell for cell in cells):
            if _target_identity(" ".join(cells)):
                return "最终动作表"
        return ""

    current_object_code_patterns = (
        r"最终观察对象[:：]\s*([^\n,，]+)",
        r"最终对象[:：]\s*([^\n,，|]+)",
        r"最终对象=([^\n]+?)\s+身份=观察对象",
        r"最终对象=([^\n]+?)\s+身份=执行对象",
        r"canonical_target=([^\n]+?)\s+role=观察对象",
        r"canonical_target=([^\n]+?)\s+role=执行对象",
    )
    for pattern in current_object_code_patterns:
        match = re.search(pattern, stripped)
        if not match:
            continue
        value_text = match.group(1)
        if any(marker in stripped for marker in process_markers) or _is_empty_target(value_text):
            return ""
        if _target_identity(value_text):
            return "最终对象传导链"

    current_line_prefixes = (
        "**观察优先对象**",
        _m("**观察优先", "锚点**"),
        "- 👀 ",
        "- ⏳ ",
        "- **跨线继续看谁**:",
        "- **盘前不抢跑**:",
        "- **确认后怎么做**:",
    )
    if not stripped.startswith(current_line_prefixes):
        return ""
    if any(marker in stripped for marker in process_markers):
        return ""
    if re.search(r"(?<!\d)\d{6}(?!\d)", stripped):
        return stripped.split(":", 1)[0].strip()
    return ""


def _audit_empty_final_object_appendix_current_object(lines):
    if not (_front_declares_no_current_object(lines) or _selection_workflow_declares_empty_final(lines)):
        return []
    appendix = _appendix_lines(lines)
    if not appendix:
        return []
    appendix_start_line = len(lines) - len(appendix)
    findings = []
    for index, line in enumerate(appendix, 1):
        label = _line_names_current_object_when_front_empty(line)
        if not label:
            continue
        findings.append(
            _finding(
                "empty_final_object_appendix_current_object_conflict",
                f"前台最终对象为空，但附录仍把具体股票写成当前对象：{label}",
                line=appendix_start_line + index,
            )
        )
    return findings


def _audit_unique_focus(lines):
    front = _front_page_lines(lines)
    findings = []
    execution_target = _extract_execution_unique_target(front)
    final_target = _extract_final_unique_target(front)
    execution_empty = _is_empty_target(execution_target)
    final_empty = _is_empty_target(final_target)
    final_is_zero_observation = (
        _final_summary_is_zero_position(front)
        and not final_empty
        and any(marker in str(final_target or "") for marker in ("观察对象", _m("观察", "锚"), "条件观察"))
    )
    if execution_empty and final_is_zero_observation:
        return findings
    if execution_empty != final_empty:
        findings.append(
            _finding(
                "unique_focus_mismatch",
                f"execution target {execution_target} conflicts with final summary target {final_target}",
            )
        )
        return findings
    if execution_empty and final_empty:
        findings.extend(_audit_empty_unique_focus_contradictions(front))
        return findings
    if _target_identity(execution_target) != _target_identity(final_target):
        findings.append(
            _finding(
                "unique_focus_mismatch",
                f"execution target {execution_target} conflicts with final summary target {final_target}",
            )
        )
        return findings
    findings.extend(
        _audit_concrete_unique_focus_evidence(
            front,
            execution_target,
            zero_position=_final_summary_is_zero_position(front),
        )
    )
    return findings


def _audit_concrete_unique_focus_evidence(front_lines, target, *, zero_position=False):
    evidence_text = "\n".join(line for line in front_lines if not str(line).lstrip().startswith("#"))
    missing = []
    families = ZERO_POSITION_UNIQUE_FOCUS_EVIDENCE_FAMILIES if zero_position else UNIQUE_FOCUS_EVIDENCE_FAMILIES
    for label, markers in families:
        if any(marker in evidence_text for marker in markers):
            continue
        missing.append(label)
    if not missing:
        return []
    return [
        _finding(
            "unique_focus_evidence_missing",
            f"concrete unique target {target} is missing front-page decision evidence: {', '.join(missing)}",
        )
    ]


def _has_stock_reference(cells):
    text = " ".join(cells)
    return bool(re.search(r"(?<!\d)\d{6}(?!\d)", text))


def _has_observation_only_qualifier(cells):
    text = " ".join(cells)
    return any(marker in text for marker in UNIQUE_FOCUS_OBSERVATION_ONLY_MARKERS)


def _has_actionable_buy_label(cells, header):
    row_text = " ".join(cells)
    if any(label in row_text for label in UNIQUE_FOCUS_BUY_LABELS):
        return True
    for index, title in enumerate(header):
        if "明日资格" not in title or index >= len(cells):
            continue
        value = cells[index].strip()
        if value in ("有", "是", "具备"):
            return True
        if any(label in value for label in UNIQUE_FOCUS_BUY_LABELS):
            return True
        if "可执行" in value or "可买" in value:
            return True
    return False


def _audit_empty_unique_focus_contradictions(front_lines):
    findings = []
    header = []
    for offset, line in enumerate(front_lines):
        cells = _split_md_row(line)
        if not cells:
            header = []
            continue
        if _is_separator_cells(cells):
            continue
        next_cells = _split_md_row(front_lines[offset + 1]) if offset + 1 < len(front_lines) else []
        if _is_separator_cells(next_cells):
            header = cells
            continue
        if not _has_stock_reference(cells):
            continue
        if _has_observation_only_qualifier(cells):
            continue
        if not _has_actionable_buy_label(cells, header):
            continue
        findings.append(
            _finding(
                "unique_focus_contradiction",
                "unique target is empty, but the front page labels a concrete stock as buyable or executable",
                line=offset + 1,
            )
        )
    return findings


def audit_report_markdown(markdown, companion_html=None):
    stopped_report_findings = _audit_stopped_report_notice(markdown)
    if stopped_report_findings is not None:
        return {
            "passed": not stopped_report_findings,
            "findings": stopped_report_findings,
            "finding_count": len(stopped_report_findings),
        }
    lines = _lines(markdown)
    findings = []
    findings.extend(_audit_legacy_daily_report_terms(lines))
    findings.extend(_audit_front_page_headings(lines))
    findings.extend(_audit_monthly_rhythm_section(lines))
    findings.extend(_audit_candidate_section_contract(lines))
    findings.extend(_audit_process_evidence_headings(lines))
    findings.extend(_audit_mainline_capacity_regime_contract(lines))
    findings.extend(_audit_legacy_surface_wording(lines))
    findings.extend(_audit_legacy_trading_time_wording(lines))
    findings.extend(_audit_execution_windows(lines))
    findings.extend(_audit_execution_conditions(lines))
    findings.extend(_audit_unique_action_target_contract(lines))
    findings.extend(_audit_b_level_conditions(lines))
    findings.extend(_audit_two_layer_execution_object_consistency(lines))
    findings.extend(_audit_front_execution_object_negation(lines))
    findings.extend(_audit_front_execution_object_downgrade(lines))
    findings.extend(_audit_appendix_duplicate_front_page_sections(lines))
    findings.extend(_audit_duplicate_no_trade(lines))
    findings.extend(_audit_front_page_duplicate_long_cells(lines))
    findings.extend(_audit_degraded_fake_zero(lines))
    findings.extend(_audit_market_breadth_incomplete(lines))
    findings.extend(_audit_position_context_contradictions(lines))
    findings.extend(_audit_account_advice_position_contract(lines))
    findings.extend(_audit_opportunity_comparison_contract(lines))
    findings.extend(_audit_incomplete_candidate_execution_plan(lines))
    findings.extend(_audit_candidate_identity_conflicts(lines))
    findings.extend(_audit_success_rates_match_request_logs(lines))
    findings.extend(_audit_market_fit_observation_count(lines))
    findings.extend(_audit_market_base_freshness(lines))
    findings.extend(_audit_market_base_readability(lines))
    findings.extend(_audit_extreme_conviction_tracking(lines))
    findings.extend(_audit_reasoning_surface(lines))
    findings.extend(_audit_anti_noise_language(lines))
    findings.extend(_audit_unique_focus(lines))
    findings.extend(audit_new_stock_visibility(markdown)["findings"])
    findings.extend(_audit_final_object_identity_consistency(lines))
    findings.extend(_audit_daily_judgment_core_candidate_consistency(lines))
    findings.extend(_audit_derivation_audit_rejection_consistency(lines))
    findings.extend(_audit_process_candidate_loss_reasons(lines))
    findings.extend(_audit_sniper_target_derivation_consistency(lines))
    findings.extend(_audit_selection_workflow_consistency(lines))
    findings.extend(_audit_observation_anchor_consistency(lines))
    findings.extend(_audit_empty_final_object_appendix_current_object(lines))
    findings.extend(_audit_zero_position_decision_attribution(lines))
    findings.extend(_audit_zero_position_tomorrow_action_consistency(lines))
    findings.extend(_audit_zero_position_participation_language(lines))
    findings.extend(_audit_chanlun_tomorrow_decision_consistency(lines, companion_html))
    findings.extend(_audit_position_state_rendering(lines))
    findings.extend(_audit_next_day_attribution_contract(lines))
    return {
        "passed": not findings,
        "findings": findings,
        "finding_count": len(findings),
    }


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description="Audit a generated daily-report markdown file.")
    parser.add_argument("markdown_path")
    parser.add_argument("--companion-html", help="Optional companion 上证缠论 HTML file to audit with the markdown.")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    path = Path(args.markdown_path)
    companion_html = None
    if args.companion_html:
        companion_html = Path(args.companion_html).read_text(encoding="utf-8")
    result = audit_report_markdown(path.read_text(encoding="utf-8"), companion_html=companion_html)
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if result["passed"]:
            print("report_acceptance_audit: passed")
        else:
            for finding in result["findings"]:
                line_suffix = f":{finding['line']}" if "line" in finding else ""
                print(f"{finding['code']}{line_suffix} {finding['message']}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
