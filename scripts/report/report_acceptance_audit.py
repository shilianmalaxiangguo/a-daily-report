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


_PENDING_TRADE_CURRENT_MARKERS = (
    "外部交易待核实",
    "外部交易记录待核实",
    "外部成交记录待核实",
)
_PENDING_TRADE_LEGACY_MARKERS = ("待成交确认",)
_PENDING_TRADE_B1_MARKERS = ("确认已成交才视为B1", "核实已成交才视为B1")
_PENDING_TRADE_NO_B2_MARKERS = ("未确认不新增B2", "未核实不新增B2")


def _has_pending_trade_wording(value):
    text = str(value or "")
    return any(
        marker in text
        for marker in _PENDING_TRADE_CURRENT_MARKERS + _PENDING_TRADE_LEGACY_MARKERS
    )


def _has_pending_trade_b1_rule(value):
    text = str(value or "")
    return any(marker in text for marker in _PENDING_TRADE_B1_MARKERS)


def _has_pending_trade_no_b2_rule(value):
    text = str(value or "")
    return any(marker in text for marker in _PENDING_TRADE_NO_B2_MARKERS)

try:
    from portfolio.position_strategy_report import (
        _read_report_day_account_state as _read_day_order_account_state,
        _read_report_day_path_target as _read_day_order_expected_path_target,
        _target_label as _day_order_target_label,
    )
except (ImportError, ModuleNotFoundError):
    _read_day_order_account_state = None
    _read_day_order_expected_path_target = None
    _day_order_target_label = None

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
    "09:35-" + "10:30",
    "10:30-" + "14:30",
    "结构" + "确认窗口",
    "盘中执行（" + "10:30-" + "14:30）",
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
    "历史过程复盘：明日极度看好近25日跟踪表",
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

LIMIT_DOWN_REVERSAL_PLAN_MARKERS = (
    "跌停反包",
    "跌停后反包",
    "跌停后修复",
    "跌停打开",
    "跌停开板",
    "跌停修复",
    "跌停反核",
    "跌停后反核",
    "跌停水下强势修复",
    "跌停后水下强势修复",
    "反核专项",
    "撬板",
    "翘板",
    "地天",
)

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
PROBABILITY_BAND_RE = re.compile(r"\b\d{1,3}%\s*[-~－—]\s*\d{1,3}%")
COARSE_PROBABILITY_LABEL_RE = re.compile(
    r"(?:胜率|后验)\s*\d{1,3}%|\d{1,3}%\s*(?:胜率|后验|概率)|概率(?:偏高|很高|较高)|(?:高概率|低概率)|(?:粗可信|可信标签)"
)
BAYESIAN_FRONT_HEADING = "### 路径诊断复盘"
BAYESIAN_APPENDIX_MARKER = "路径诊断复盘"
BAYESIAN_SOURCE_DATE_MISSING = "来源日期缺失"


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
POSITION_STYLE_GRADE_MARKERS = ("0%不参与", "50%条件执行", "满仓条件执行", "100%核心进攻")
LEGACY_OBSERVATION_SURFACE_MARKERS = (
    _m("观察", "锚"),
    _m("观察", "锚点"),
    _m("观察优先", "锚点"),
    _m("最终观察", "锚"),
    _m("只看观察", "锚"),
)
ZERO_POSITION_ACTION_MARKERS = ("明日主买对象", "明日补位对象", "新增参与", _m("条件", "50%"), "50%条件执行", "才评估50%条件执行")
ZERO_POSITION_CURRENT_DECISION_ACTION_LABELS = ("主买对象", "补位对象")
ZERO_POSITION_NO_ACTION_ROW_MARKERS = (
    "不新增参与",
    "不构成明日新增参与",
    "没有新增参与资格",
    "禁止新增参与",
    "不能新增参与",
    "不具备新增参与资格",
    "不取得新增参与资格",
    "不能转成新增参与",
    "不能取得新增参与资格",
    "暂无新增参与资格",
    "未给出新增参与资格",
    "无明日执行对象",
)
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
    "条件满足才50%条件执行",
    "参与窗口" + "命中后才评估50%条件执行",
    "固定交易窗口条件成立才参与",
    "固定交易窗口条件成立才50%条件执行",
    "观察对象重新成立",
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
EXTREME_CONVICTION_TRACKING_HISTORICAL_HEADING = "**历史过程复盘：明日极度看好近25日跟踪表**"
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
    "🟢 跟随主线",
    "B1先到1x/50%取得参与权",
    "按昨晚1x/50%半仓预案检查B1执行资格",
    "市场已允许参与",
    "市场允许参与",
    "窗口条件成立才参与",
    "买也只买最强",
    "最终操作状态**: 进攻态",
    "次日市场环境**: 只观察 / 进攻态",
    "明日市场环境：只观察 / 进攻态",
    "日线预估买入区间**:",
    "硬止损底线**:",
    "止盈观察位**:",
    "买入后按失效价",
    "买后用失效价",
)
ZERO_POSITION_ALLOWED_PARTICIPATION_MARKERS = (
    "不参与",
    "不新增参与",
    "不构成明日新增参与",
    "没有新增参与资格",
    "禁止新增参与",
    "不能新增参与",
    "不具备新增参与资格",
    "不取得新增参与资格",
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


def _parse_visible_number(value):
    match = re.search(r"[+-]?\d+(?:\.\d+)?", str(value or "").replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _table_rows_after_heading(lines, heading):
    rows = []
    in_section = False
    for line in lines:
        text = str(line or "").strip()
        if text == heading:
            in_section = True
            continue
        if not in_section:
            continue
        if text.startswith("#") and text != heading:
            break
        cells = _split_md_row(text)
        if not cells or _is_separator_cells(cells):
            continue
        rows.append(cells)
    return rows


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
                f"{artifact_label}缺少可读取内容",
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
                f"前台结论为0%不参与，但{artifact_label}仍包含新增参与动作",
            )
        ]
    front_target = _extract_final_unique_target(front)
    front_identity = _target_identity(front_target)
    front_pct = _parse_percent_int(_extract_final_execution_style(front))
    if front_pct is not None and final_pct is not None and front_pct != final_pct:
        return [
            _finding(
                conflict_code,
                f"前台最终仓位{front_pct}%与{artifact_label}最终仓位{final_pct}%不一致",
            )
        ]
    if front_identity and not final_identity and (front_pct or 0) > 0:
        return [
            _finding(
                conflict_code,
                f"前台最终对象{front_target}没有出现在{artifact_label}最终动作中",
            )
        ]
    if front_identity and final_identity and front_identity != final_identity:
        return [
            _finding(
                conflict_code,
                f"前台最终对象{front_target}与{artifact_label}最终对象{final_identity}不一致",
            )
        ]
    return []


def _audit_elimination_tournament_consistency(lines, companion_html):
    return _audit_companion_final_action_consistency(
        lines,
        _extract_elimination_tournament_payload(companion_html),
        artifact_label="淘汰赛伴随HTML",
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
    "cycle_window",
    "counter_evidence_account",
    "final_action",
)


REQUIRED_SECTOR_CAPITAL_PREFLIGHT_DECISIONS = (
    "市场能否进攻",
    "哪个板块被选择",
    "谁是资金载体",
    "是否有量化参与痕迹",
    "价格行为是否接受",
    "周期窗口是否打开",
    "账户是否适配",
)


def _audit_sector_capital_preflight_payload_contract(payload):
    if payload is None or not payload:
        return []
    findings = []
    final_action = payload.get("final_action") if isinstance(payload.get("final_action"), dict) else {}
    final_target = final_action.get("target") if isinstance(final_action.get("target"), dict) else {}
    final_identity = _target_identity(final_target.get("code") or final_target.get("name") or "")
    final_pct = _parse_percent_int(str(final_action.get("position_pct", "")))
    if final_pct is None:
        final_pct = _parse_percent_int(final_action.get("label", ""))
    zero_final_action_without_target = bool(final_action) and final_pct == 0 and not final_identity
    if payload.get("derivation_contract") != "sector_capital_diffusion_first.v1":
        findings.append(
            _finding(
                "sector_capital_preflight_contract_missing",
                "板块资金复核数据包缺少板块资金优先推导口径",
            )
        )
    mermaid = str(payload.get("mermaid") or "")
    for text in ("周期窗口", "唯一明日动作或不参与", "白痴指数复核", "压缩/合并/降级低价值高成本层"):
        if text not in mermaid:
            findings.append(
                _finding(
                    "sector_capital_preflight_mermaid_incomplete",
                    f"板块资金复核流程图缺少：{text}",
                )
            )
    layers = payload.get("layers") if isinstance(payload.get("layers"), list) else []
    layer_ids = [str(layer.get("id") or "") for layer in layers if isinstance(layer, dict)]
    missing_layers = [layer_id for layer_id in REQUIRED_SECTOR_CAPITAL_PREFLIGHT_LAYERS if layer_id not in layer_ids]
    if missing_layers:
        findings.append(
            _finding(
                "sector_capital_preflight_layers_missing",
                "板块资金复核数据包缺少层级：" + ", ".join(missing_layers),
            )
        )
    previous_survivor_keys = None
    previous_layer_id = ""
    for layer in layers:
        if not isinstance(layer, dict):
            continue
        entries = layer.get("entries") if isinstance(layer.get("entries"), list) else []
        input_entries = entries
        if layer.get("id") == "final_action" and zero_final_action_without_target:
            input_entries = [
                entry
                for entry in entries
                if not (isinstance(entry, dict) and entry.get("status") == "final_action")
            ]
        eliminated = [entry for entry in entries if isinstance(entry, dict) and entry.get("status") == "eliminated"]
        if layer.get("id") == "final_action":
            survivors = [
                entry
                for entry in entries
                if isinstance(entry, dict)
                and entry.get("status") in {"final_action", "survived"}
                and _target_identity(entry.get("stock_code") or entry.get("stock_name") or "")
            ]
        else:
            survivors = [entry for entry in entries if isinstance(entry, dict) and entry.get("status") == "survived"]
        input_keys = {
            _target_identity((entry.get("stock_code") or entry.get("stock_name") or "") if isinstance(entry, dict) else "")
            for entry in input_entries
        }
        input_keys = {key for key in input_keys if key}
        survivor_keys = {
            _target_identity((entry.get("stock_code") or entry.get("stock_name") or "") if isinstance(entry, dict) else "")
            for entry in survivors
        }
        survivor_keys = {key for key in survivor_keys if key}
        if (
            previous_survivor_keys is not None
            and not input_keys.issubset(previous_survivor_keys)
        ):
            findings.append(
                _finding(
                    "sector_capital_preflight_layer_sequence_mismatch",
                    f"板块资金复核层级 {layer.get('id')} 引入了不在上一层剩余名单中的股票；上一层={previous_layer_id}",
                )
            )
        previous_survivor_keys = survivor_keys
        previous_layer_id = str(layer.get("id") or "")
        if int(layer.get("input_count") or 0) != len(input_entries):
            findings.append(
                _finding(
                    "sector_capital_preflight_layer_count_mismatch",
                    f"板块资金复核层级 {layer.get('id')} 输入数量与明细不一致",
                )
            )
        if int(layer.get("eliminated_count") or 0) != len(eliminated):
            findings.append(
                _finding(
                    "sector_capital_preflight_layer_count_mismatch",
                    f"板块资金复核层级 {layer.get('id')} 排除数量与明细不一致",
                )
            )
        if int(layer.get("survivor_count") or 0) != len(survivors):
            findings.append(
                _finding(
                    "sector_capital_preflight_layer_count_mismatch",
                    f"板块资金复核层级 {layer.get('id')} 剩余数量与明细不一致",
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
                        f"板块资金复核层级 {layer.get('id')} 明细缺少字段："
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
                "板块资金复核决策清单缺少：" + ", ".join(missing_decisions),
            )
        )
    idiot_rows = payload.get("idiot_index_review") if isinstance(payload.get("idiot_index_review"), list) else []
    if not idiot_rows:
        findings.append(
            _finding(
                "sector_capital_preflight_idiot_index_missing",
                "板块资金复核数据包缺少白痴指数复核行",
            )
        )
    tplus_rehearsal = payload.get("tplus_rehearsal") if isinstance(payload.get("tplus_rehearsal"), dict) else {}
    if not tplus_rehearsal:
        findings.append(
            _finding(
                "sector_capital_preflight_tplus_rehearsal_missing",
                "板块资金复核数据包缺少T+1/T+2推演",
            )
        )
    else:
        if tplus_rehearsal.get("schema_version") != "t0_tplus_rehearsal.v1":
            findings.append(
                _finding(
                    "sector_capital_preflight_tplus_rehearsal_missing",
                    "板块资金复核T+1/T+2推演版本不匹配",
                )
            )
        for section_key in ("tplus1", "tplus2"):
            section = tplus_rehearsal.get(section_key) if isinstance(tplus_rehearsal.get(section_key), dict) else {}
            missing_fields = [
                field
                for field in ("market_emotion", "market_cycle", "sector_emotion", "sector_cycle", "action")
                if not section.get(field)
            ]
            if missing_fields:
                findings.append(
                    _finding(
                        "sector_capital_preflight_tplus_rehearsal_missing",
                        f"板块资金复核 {section_key} 推演缺少："
                        + ", ".join(missing_fields),
                    )
                )
    return findings


def _audit_sector_capital_preflight_consistency(lines, companion_html):
    payload = _extract_sector_capital_preflight_payload(companion_html)
    findings = _audit_companion_final_action_consistency(
        lines,
        payload,
        artifact_label="板块资金复核伴随HTML",
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
                "首页标题必须在附录前按固定顺序各出现一次",
            )
        )
    for heading in FRONT_PAGE_HEADINGS:
        if headings.count(heading) > 1:
            findings.append(_finding("duplicate_front_page_heading", f"首页标题重复：{heading}"))
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
                    f"首页执行计划缺少必要时间窗口：{window}",
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
                f"首页执行计划已有时间窗口，但缺少必要执行条件：{label}",
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
                    "快速执行窗口必须展示竞价、开盘或回封步骤，不能只写结构条件",
                    line=offset,
                )
            )
        if is_fast_window and fallback != "不满足回到0%":
            findings.append(
                _finding(
                    "fast_window_fallback_not_zero",
                    "快速参与窗口未触发预案时必须回到0%",
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
                    "首页必须使用进攻仓位三态，不再使用今日信号等级",
                    line=offset,
                )
            )
        if cells and cells[0] == "仓位攻击等级":
            findings.append(
                _finding(
                    "legacy_position_grade_label",
                    "首页必须使用进攻仓位三态，不再使用仓位攻击等级",
                    line=offset,
                )
            )
    if MONTHLY_RHYTHM_HEADING not in front:
        findings.append(
            _finding(
                "monthly_rhythm_missing",
                "首页必须在选股前展示月度攻防节奏",
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
                        f"月度攻防节奏缺少必要字段：{label}",
                    )
            )
    attack_grade = section_values.get("进攻仓位三态")
    if attack_grade is not None and attack_grade not in POSITION_ATTACK_GRADE_LABELS:
        findings.append(
                _finding(
                    "position_attack_grade_invalid",
                    "进攻仓位三态只能是0%、50%或100%",
                )
        )
    max_position_text = section_values.get("明日最大仓位")
    if max_position_text == "满仓或0%不参与":
        max_position = 100
    else:
        max_position = _parse_percent_int(max_position_text)
    min_position = POSITION_ATTACK_GRADE_MIN_POSITION.get(attack_grade)
    if max_position is not None and min_position is not None and min_position > max_position:
        findings.append(
                _finding(
                    "position_attack_grade_exceeds_max_position",
                    "进攻仓位三态不能超过明日最大仓位允许范围",
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
                    f"首页个股部分必须使用个股裁决 / 备用观察，不再使用旧标题：{line}",
                    line=index,
                )
            )
    if "## 五、个股解读" in front and "### 1. 个股裁决" not in front:
        findings.append(
            _finding(
                "candidate_verdict_missing",
                "首页个股部分必须展示带当前状态的个股裁决",
            )
        )
    stock_section = "\n".join(_section_after(front, "### 1. 个股裁决"))
    if stock_section and "| 当前状态 |" not in stock_section:
        findings.append(
                _finding(
                    "candidate_state_missing",
                    "首页个股裁决必须包含当前状态",
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
                    "首页主线部分必须使用主线容量与格局判断，不再使用旧版双主线表",
                    line=index,
                )
            )
    if MAINLINE_CAPACITY_REGIME_HEADING not in front or MAINLINE_CAPACITY_REGIME_HEADER not in front:
        findings.append(
            _finding(
                "mainline_capacity_regime_missing",
                "首页周期部分必须展示主线容量与格局判断",
            )
        )
    if MAINLINE_ATTACK_EVIDENCE_HEADING not in front or MAINLINE_ATTACK_EVIDENCE_HEADER not in front:
        findings.append(
            _finding(
                "mainline_attack_evidence_missing",
                "首页周期部分必须展示主线攻击证据",
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
                    f"报告必须使用资格/条件/可做表述，不再使用旧口径：{marker}",
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
                f"报告必须使用固定交易窗口，不再使用旧时间表述：{marker}",
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
                    f"附录重复首页章节标题：{heading}",
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
        if not re.search(r"(?<!\d)0\.00%", text):
            continue
        if any(marker in text for marker in DEGRADED_MARKERS):
            findings.append(
                _finding(
                    "degraded_fake_zero_percent",
                    "数据缺失或降级时不能渲染成真实0.00%",
                    line=index,
                )
            )
    return findings


def _audit_turnover_core_quote_completeness(lines):
    findings = []
    in_section = False
    section_line = None
    table_found = False
    headers = []
    header_indexes = {}
    for index, line in enumerate(lines or [], 1):
        text = str(line or "").strip()
        if text.startswith("#"):
            if "成交核心结果" in text:
                in_section = True
                section_line = index
                headers = []
                header_indexes = {}
                continue
            if in_section:
                break
        if not in_section:
            continue
        cells = _split_md_row(text)
        if not cells or _is_separator_cells(cells):
            continue
        if not headers:
            if not {"排名", "股票", "成交额"}.issubset(set(cells)):
                continue
            table_found = True
            headers = cells
            header_indexes = {header: offset for offset, header in enumerate(headers)}
            if "涨跌幅" not in header_indexes:
                findings.append(
                    _finding(
                        "turnover_core_change_pct_missing",
                        "成交核心结果必须展示涨跌幅",
                        line=index,
                    )
                )
            continue
        if "涨跌幅" not in header_indexes:
            continue
        required_price_headers = ("最高价", "最低价", "开盘价", "收盘价")
        if not all(header in header_indexes for header in required_price_headers):
            continue
        change_index = header_indexes["涨跌幅"]
        price_indexes = [header_indexes[header] for header in required_price_headers]
        if max([change_index, *price_indexes], default=-1) >= len(cells):
            continue
        change_pct = _parse_visible_number(cells[change_index])
        prices = [_parse_visible_number(cells[offset]) for offset in price_indexes]
        if change_pct == 0 and all(price == 0 for price in prices):
            findings.append(
                _finding(
                    "turnover_core_fake_zero_quote",
                    "成交核心结果缺少真实报价，不能把涨跌幅和价格写成0",
                    line=index,
                )
            )
    if section_line is not None and not table_found:
        findings.append(
            _finding(
                "turnover_core_table_missing",
                "成交核心结果缺少可识别的成交排行表，关键数据不完整，停止生成",
                line=section_line,
            )
        )
    return findings


def _turnover_core_table_rows(lines):
    in_section = False
    headers = []
    rows = []
    for index, line in enumerate(lines or [], 1):
        text = str(line or "").strip()
        if text.startswith("#"):
            if "成交核心结果" in text:
                in_section = True
                headers = []
                rows = []
                continue
            if in_section:
                break
        if not in_section:
            continue
        cells = _split_md_row(text)
        if not cells or _is_separator_cells(cells):
            continue
        if not headers:
            if {"排名", "股票", "成交额"}.issubset(set(cells)):
                headers = cells
            continue
        if cells and _parse_visible_number(cells[0]) is not None:
            rows.append((index, cells))
    return headers, rows


def _first_expected_number(row, keys):
    if not isinstance(row, dict):
        return None
    for key in keys:
        value = row.get(key)
        if value in (None, ""):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _first_expected_text(row, keys):
    if not isinstance(row, dict):
        return ""
    for key in keys:
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def _six_digit_code(value):
    match = re.search(r"(?<!\d)(\d{6})(?!\d)", str(value or ""))
    return match.group(1) if match else str(value or "").strip()


def _expected_turnover_row_has_complete_prices(row):
    price_key_groups = (
        ("open", "开盘价", "开盘"),
        ("high", "最高价", "最高"),
        ("low", "最低价", "最低"),
        ("close", "收盘价", "收盘", "price", "最新价", "当前价"),
    )
    return all(
        (value := _first_expected_number(row, keys)) is not None and value > 0
        for keys in price_key_groups
    )


def _audit_turnover_core_source_consistency(lines, expected_rows):
    expected = [row for row in (expected_rows or []) if isinstance(row, dict)][:30]
    if not expected:
        return []
    headers, rendered_rows = _turnover_core_table_rows(lines)
    if not headers:
        return []

    findings = []
    if len(rendered_rows) != len(expected):
        findings.append(
            _finding(
                "turnover_core_source_mismatch",
                f"成交核心结果行数与源事实不一致：日报{len(rendered_rows)}行，源事实{len(expected)}行",
                line=rendered_rows[0][0] if rendered_rows else None,
            )
        )

    header_indexes = {header: offset for offset, header in enumerate(headers)}
    numeric_fields = (
        ("成交额", ("turnover", "amount_yi")),
        ("涨跌幅", ("change_pct", "pct_chg", "pct_change", "涨跌幅", "zdf", "change_rate", "change")),
        ("最高价", ("high", "最高价", "最高")),
        ("最低价", ("low", "最低价", "最低")),
        ("开盘价", ("open", "开盘价", "开盘")),
        ("收盘价", ("close", "收盘价", "收盘", "price", "最新价", "当前价")),
    )
    for position, ((line_number, cells), source_row) in enumerate(zip(rendered_rows, expected), 1):
        mismatches = []
        rank_index = header_indexes.get("排名", -1)
        actual_rank = _parse_visible_number(cells[rank_index]) if 0 <= rank_index < len(cells) else None
        expected_rank = _first_expected_number(source_row, ("rank", "rank_no"))
        if expected_rank is None:
            expected_rank = float(position)
        if actual_rank != expected_rank:
            mismatches.append("排名")

        name_index = header_indexes.get("股票", -1)
        actual_name = cells[name_index].strip() if 0 <= name_index < len(cells) else ""
        expected_name = _first_expected_text(source_row, ("name", "stock_name", "名称"))
        if expected_name and actual_name != expected_name:
            mismatches.append("股票")

        code_index = header_indexes.get("代码", -1)
        actual_code = _six_digit_code(cells[code_index]) if 0 <= code_index < len(cells) else ""
        expected_code = _six_digit_code(_first_expected_text(source_row, ("code", "stock_code", "ts_code", "代码")))
        if expected_code and actual_code != expected_code:
            mismatches.append("代码")

        for header, source_keys in numeric_fields:
            source_value = _first_expected_number(source_row, source_keys)
            if source_value is None:
                continue
            if header == "涨跌幅" and source_value == 0 and not _expected_turnover_row_has_complete_prices(source_row):
                continue
            cell_index = header_indexes.get(header, -1)
            actual_value = _parse_visible_number(cells[cell_index]) if 0 <= cell_index < len(cells) else None
            if actual_value is None or f"{actual_value:.2f}" != f"{source_value:.2f}":
                mismatches.append(header)

        if mismatches:
            findings.append(
                _finding(
                    "turnover_core_source_mismatch",
                    f"成交核心结果第{position}行与源事实不一致：{'、'.join(mismatches)}",
                    line=line_number,
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
    current_lines = []
    inside_trade_principles = False
    for index, line in enumerate(lines, 1):
        stripped = str(line or "").strip()
        if stripped == "## 交易原则":
            inside_trade_principles = True
            continue
        if inside_trade_principles and stripped.startswith("## "):
            inside_trade_principles = False
        if inside_trade_principles:
            continue
        cells = _split_md_row(line)
        if cells and cells[0] in {"Ta", "Tb", "Tc"}:
            continue
        current_lines.append((index, line))
    full_text = "\n".join(str(line or "") for _, line in current_lines)
    no_holding_markers = ("无昨日持仓", "无持仓负担", "无旧仓")
    current_empty_account_markers = (
        "| 操作风格 | 空仓 |",
        "当前没有能下手的票，明日空仓观察",
        "- ✅ 保持空仓：当前不新增参与",
        "- **现在到底是什么状态**: 空仓",
        "- **明天仓位放多少**: 0%（保持空仓）",
        "空仓等待，禁止参与；若你有仓位，只做退出不做幻想",
    )
    unknown_position_markers = ("未输入持仓", "持仓未输入")
    unknown_conflict_markers = no_holding_markers + current_empty_account_markers
    findings = []
    if any(marker in full_text for marker in unknown_position_markers) and any(
        marker in full_text for marker in unknown_conflict_markers
    ):
        for index, line in current_lines:
            if any(marker in str(line or "") for marker in unknown_conflict_markers):
                findings.append(
                    _finding(
                        "unknown_position_rendered_as_no_holding",
                        "未输入持仓时不能渲染成无持仓结论",
                        line=index,
                    )
                )
                break
    if "已有昨日持仓" in full_text and any(marker in full_text for marker in no_holding_markers):
        for index, line in current_lines:
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


def _extract_html_timeline_assets(companion_html):
    text = str(companion_html or "")
    if "position-timeline-shell" not in text:
        return {}
    assets = {}
    row_pattern = re.compile(
        r'<tr\b[^>]*class=["\'][^"\']*timeline-row-(?P<lane>ta|tb|tc|td|te)[^"\']*["\'][^>]*>(?P<body>.*?)</tr>',
        re.I | re.S,
    )
    for match in row_pattern.finditer(text):
        body = match.group("body")
        name_match = re.search(r'<span\b[^>]*class=["\']timeline-asset-name["\'][^>]*>(.*?)</span>', body, re.I | re.S)
        code_match = re.search(r'<span\b[^>]*class=["\']timeline-asset-code["\'][^>]*>(.*?)</span>', body, re.I | re.S)
        empty_match = re.search(r'<span\b[^>]*class=["\']timeline-asset-empty["\'][^>]*>(.*?)</span>', body, re.I | re.S)
        if name_match:
            name = html.unescape(re.sub(r"<[^>]+>", "", name_match.group(1))).strip()
            code = html.unescape(re.sub(r"<[^>]+>", "", code_match.group(1))).strip() if code_match else ""
            assets[match.group("lane").lower()] = f"{name}({code})" if code else name
        elif empty_match:
            assets[match.group("lane").lower()] = html.unescape(re.sub(r"<[^>]+>", "", empty_match.group(1))).strip()
    return assets


def _extract_html_timeline_row_markup(companion_html, lane):
    text = str(companion_html or "")
    match = re.search(
        rf'<tr\b[^>]*class=["\'][^"\']*timeline-row-{re.escape(str(lane or "").lower())}[^"\']*["\'][^>]*>(.*?)</tr>',
        text,
        re.I | re.S,
    )
    if not match:
        return ""
    return match.group(1)


def _extract_html_timeline_row_text(companion_html, lane):
    markup = _extract_html_timeline_row_markup(companion_html, lane)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", markup))).strip()


def _markdown_has_position_timeline(lines):
    for line in lines:
        text = str(line or "").lstrip()
        if text.startswith("| 轨道 | 标的 |") or text.startswith("| 日序 | 日期 |"):
            return True
    return False


def _audit_position_timeline_parity(lines, companion_html=None, *, require_html_timeline=False):
    html_assets = _extract_html_timeline_assets(companion_html)
    html_has_timeline = bool(html_assets) or "position-day-order-shell" in str(companion_html or "")
    markdown_has_timeline = _markdown_has_position_timeline(lines)
    findings = []
    if html_has_timeline and not markdown_has_timeline:
        findings.append(
            _finding(
                "position_timeline_markdown_missing",
                "Bear HTML 已有账户日序图时，Markdown 也必须写出同一张可读表",
            )
        )
    if require_html_timeline and not html_has_timeline:
        findings.append(
            _finding(
                "position_timeline_html_missing",
                "Bear HTML 缺少账户日序表，关键数据不完整，停止生成",
            )
        )
    if html_has_timeline:
        for _offset, cells in _extract_day_order_rows(lines):
            lane = cells[0].lower()
            unknown_account = any(
                marker in " ".join(cells[2:6])
                for marker in (
                    "持仓未输入",
                    "先确认是否已有旧仓",
                    "旧仓事实不清",
                    "先核对实际持仓",
                    "账户仓位待确认",
                )
            )
            if lane in {"ta", "tb", "tc"} and "持仓未输入" in cells[2] and html_assets.get(lane) != "持仓未输入":
                findings.append(
                    _finding(
                        "position_day_order_html_unknown_rendered_as_empty",
                        f"Bear HTML 必须保留 {cells[0]} 的持仓未输入，不能显示为空仓；停止生成",
                    )
                )
            row_markup = _extract_html_timeline_row_markup(companion_html, lane)
            empty_badge = re.search(
                r'class=["\'][^"\']*timeline-action-badge[^"\']*\bis-empty\b[^"\']*["\']',
                row_markup,
                re.I,
            )
            pending_badge = re.search(
                r'<span\b[^>]*class=["\'](?=[^"\']*\btimeline-action-badge\b)(?=[^"\']*\bis-check\b)[^"\']*["\'][^>]*>\s*待确认\s*</span>',
                row_markup,
                re.I,
            )
            if unknown_account and empty_badge:
                findings.append(
                    _finding(
                        "position_day_order_html_unknown_rendered_as_empty",
                        f"Bear HTML 必须保留 {cells[0]} 的待确认动作，不能显示为空仓；停止生成",
                    )
                )
            elif unknown_account and not pending_badge:
                findings.append(
                    _finding(
                        "position_day_order_html_unknown_pending_badge_missing",
                        f"Bear HTML 必须显示 {cells[0]} 的待确认动作；停止生成",
                    )
                )
    old_asset = html_assets.get("ta", "")
    ta_pending_plan = False
    for _offset, cells in _extract_day_order_rows(lines):
        if cells[0].lower() != "ta":
            continue
        pending_match = re.fullmatch(
            r"最远复盘日(?:计划待成交确认|外部交易待核实)[：:]\s*(.+)",
            cells[2],
        )
        if (
            pending_match
            and not any(marker in cells[2] for marker in ("旧仓", "历史持仓", "已确认持仓"))
            and any(
                marker in cells[4]
                for marker in (
                    "未确认成交",
                    "未核实成交",
                    "B1事实待确认",
                    "确认已成交才视为B1",
                    "核实已成交才视为B1",
                )
            )
            and _target_identity(pending_match.group(1)) == _target_identity(old_asset)
            and _target_identity(cells[3]) == _target_identity(old_asset)
        ):
            ta_pending_plan = True
            break
    if old_asset and old_asset not in {"无", "空仓", "持仓未输入", "-"} and not ta_pending_plan:
        current_lines = []
        for line in lines:
            cells = _split_md_row(line)
            if len(cells) >= 6 and cells[0] in {"Ta", "Tb", "Tc"}:
                continue
            current_lines.append(str(line or ""))
        current_text = "\n".join(current_lines)
        if "持仓未输入" in current_text:
            findings.append(
                _finding(
                    "known_old_position_conflicts_with_unknown_holding",
                    f"Ta旧仓已指向 {old_asset}，正文不能继续写持仓未输入",
                )
            )
    return findings


def _extract_position_timeline_tb_target(lines):
    for offset, line in enumerate(_front_page_lines(lines), 1):
        cells = _split_md_row(line)
        if len(cells) >= 2 and cells[0] == "Tb明日目标":
            return cells[1], offset
        if len(cells) >= 4 and cells[0] == "Te":
            execution_text = " ".join(cells[2:6])
            if any(
                marker in execution_text
                for marker in (
                    "只处理旧仓",
                    "旧仓风险",
                    "外部交易待核实",
                    "外部交易记录待核实",
                    "待成交确认",
                    "确认已成交才视为B1",
                    "核实已成交才视为B1",
                    "没有B2",
                )
            ):
                return "", None
            return cells[3], offset
    return "", None


def _audit_position_timeline_final_conflict(lines):
    tb_target, offset = _extract_position_timeline_tb_target(lines)
    if not _target_identity(tb_target):
        return []
    front = _front_page_lines(lines)
    final_target = _extract_final_unique_target(front)
    final_identity = _target_identity(final_target)
    tb_identity = _target_identity(tb_target)
    if final_identity and not _is_empty_target(final_target) and tb_identity != final_identity:
        return [
            _finding(
                "position_timeline_final_conflict",
                f"账户日序目标 {tb_target} 与最终对象 {final_target} 不一致",
                line=offset,
            )
        ]
    front_execution_object = _extract_front_execution_object(lines)
    final_empty = (
        _selection_workflow_declares_empty_final(lines)
        or _final_summary_is_zero_position(front)
        or (bool(front_execution_object) and _is_empty_target(front_execution_object))
    )
    if not final_empty:
        return []
    return [
        _finding(
            "position_timeline_final_conflict",
            f"最终动作是不参与或无执行对象，但账户日序目标写了 {tb_target}",
            line=offset,
        )
    ]


def _day_order_date(value):
    match = re.search(r"\d{4}-\d{2}-\d{2}", str(value or ""))
    return match.group(0) if match else ""


def _extract_day_order_rows(lines):
    rows = []
    for offset, line in enumerate(_front_page_lines(lines), 1):
        cells = _split_md_row(line)
        if len(cells) >= 6 and cells[0] in {"Ta", "Tb", "Tc", "Td", "Te"}:
            rows.append((offset, cells))
    return rows


def _declared_final_execution_target(lines):
    front = _front_page_lines(lines)
    front_execution_object = _extract_front_execution_object(lines)
    return front_execution_object if front_execution_object else _extract_final_unique_target(front)


def _day_order_has_pending_previous_plan(rows):
    for _offset, cells in rows:
        if cells[0] not in {"Td", "Te"}:
            continue
        text = " ".join(cells[2:6])
        if _has_pending_trade_wording(text) and (
            any(marker in text for marker in _PENDING_TRADE_CURRENT_MARKERS)
            or "前日报计划" in text
            or "计划推定" in text
            or _has_pending_trade_b1_rule(text)
        ):
            return True
    return False


def _audit_position_day_order_execution_target(lines, companion_html=None):
    rows = _extract_day_order_rows(lines)
    te_row = next(((offset, cells) for offset, cells in rows if cells[0] == "Te"), None)
    if te_row is None:
        return []

    pending_trade = _day_order_has_pending_previous_plan(rows)
    te_offset, te_cells = te_row
    markdown_target_identity = _target_identity(te_cells[3])
    declared_target_identity = _target_identity(_declared_final_execution_target(lines))
    findings = []
    if pending_trade and markdown_target_identity != declared_target_identity:
        findings.append(
            _finding(
                "position_day_order_inferred_target_conflict",
                "Te执行目标必须与日报最终执行对象一致，不能沿用外部待核实对象；停止生成",
                line=te_offset,
            )
        )

    html_assets = _extract_html_timeline_assets(companion_html)
    if "te" in html_assets:
        html_target_identity = _target_identity(html_assets.get("te", ""))
        if html_target_identity != markdown_target_identity:
            findings.append(
                _finding(
                    "position_day_order_html_inferred_target_conflict"
                    if pending_trade
                    else "position_day_order_html_target_conflict",
                    "Bear HTML 的Te必须与Markdown账户日序的Te执行目标一致；停止生成",
                )
            )
    return findings


def _expected_current_position_codes(lines, expected_position_summary=None):
    expected = expected_position_summary if isinstance(expected_position_summary, dict) else {}
    if expected.get("has_position") or expected.get("has_pending_position") or (
        expected.get("inferred_from_previous_report") is True
        or expected.get("position_source") == "previous_report_target_default_1x"
    ):
        expected_text = " ".join(
            str(expected.get(key) or "")
            for key in ("name", "stock_name", "code", "stock_code", "summary")
        )
        codes = _stock_codes_in_text(expected_text)
        if codes:
            return codes
    codes = set()
    for line in _front_page_lines(lines):
        text = str(line or "")
        cells = _split_md_row(text)
        label = cells[0] if cells else ""
        if label not in {"旧仓处理", "持仓确认", "外部交易核实", "已有旧仓", "当前持仓"} and not any(
            marker in text for marker in ("已有旧仓：", "已有旧仓:")
        ):
            continue
        if any(marker in text for marker in ("无旧仓", "持仓未输入", "已清仓")):
            continue
        codes.update(_stock_codes_in_text(text))
    return codes


def _audit_position_day_order_current_position(
    lines,
    *,
    companion_html=None,
    expected_position_summary=None,
):
    expected = expected_position_summary if isinstance(expected_position_summary, dict) else {}
    expected_codes = _expected_current_position_codes(lines, expected_position_summary)
    if not expected_codes:
        return []
    inferred_position = bool(
        expected.get("has_pending_position") is True
        and expected.get("has_position") is not True
    )
    inferred_verification_only = inferred_position and not _target_identity(
        _declared_final_execution_target(lines)
    )
    inferred_confirmed_markers = (
        "旧仓进入复核",
        "只处理旧仓风险",
        "已有1x",
        "同股旧仓1x",
        "旧仓1x",
        "已有同股旧仓",
        "已有昨日持仓",
        "同股T",
        "旧仓处理",
        "先处理旧仓",
        "持有100%",
        "默认1x旧仓",
        "上一份日报明日标的默认1x旧仓",
        "旧仓按旧路径",
    )
    inferred_global_stale_markers = (
        "默认1x旧仓",
        "上一份日报明日标的默认1x旧仓",
        "旧仓按旧路径",
    )
    td_row = next(
        ((offset, cells) for offset, cells in _extract_day_order_rows(lines) if cells[0] == "Td"),
        None,
    )
    te_row = next(
        ((offset, cells) for offset, cells in _extract_day_order_rows(lines) if cells[0] == "Te"),
        None,
    )
    findings = []
    if td_row is None:
        findings.append(
            _finding(
                "position_day_order_current_position_missing",
                "正文已有旧仓对象，但账户日序缺少Td报告日行，关键数据不完整，停止生成",
            )
        )
    else:
        offset, cells = td_row
        visible_codes = _stock_codes_in_text(f"{cells[2]} {cells[3]}")
        missing_codes = sorted(expected_codes - visible_codes)
        if missing_codes:
            findings.append(
                _finding(
                    "position_day_order_current_position_missing",
                    "正文或数据库已有旧仓对象，但Td没有写出同一股票："
                    + "、".join(missing_codes)
                    + "；关键数据不完整，停止生成",
                    line=offset,
                )
            )
        elif inferred_position:
            td_text = " ".join(cells[2:6])
            if (
                not _has_pending_trade_wording(td_text)
                or any(marker in td_text for marker in inferred_confirmed_markers)
            ):
                findings.append(
                    _finding(
                        "position_day_order_inferred_confirmation_missing",
                        "Td虽然写出了待核实交易对象，但没有保留外部交易待核实口径；停止生成",
                        line=offset,
                    )
                )
    if inferred_position:
        if te_row is None:
            findings.append(
                _finding(
                    "position_day_order_inferred_confirmation_missing",
                    "外部交易待核实时，账户日序缺少Te执行日行；停止生成",
                )
            )
        else:
            te_offset, te_cells = te_row
            te_text = " ".join(te_cells[2:6])
            te_target_identity = _target_identity(te_cells[3])
            te_tracks_inferred_position = (
                not te_target_identity
                or bool(_stock_codes_in_text(te_cells[3]) & expected_codes)
            )
            if te_tracks_inferred_position and (
                not _has_pending_trade_wording(te_text)
                or not _has_pending_trade_b1_rule(te_text)
                or not _has_pending_trade_no_b2_rule(te_text)
                or (
                    inferred_verification_only
                    and ("0%不参与" not in te_text or "只核实" not in te_text)
                )
                or any(marker in te_text for marker in inferred_confirmed_markers)
            ):
                findings.append(
                    _finding(
                        "position_day_order_inferred_confirmation_missing",
                        "Te没有保留外部交易待核实口径；停止生成",
                        line=te_offset,
                    )
                )
        for offset, line in enumerate(lines, 1):
            cells = _split_md_row(line)
            label = cells[0] if cells else ""
            current_action_labels = {
                "账户约束",
                "明日仓位",
                "明日新仓",
                "账户风险暴露",
                "明日动作",
                "账户后台任务负担",
                "持仓优先动作",
                "明天是否参与",
                "市场情绪状态",
            }
            stale_global_wording = any(marker in line for marker in inferred_global_stale_markers)
            stale_current_action = label in current_action_labels and any(
                marker in line for marker in inferred_confirmed_markers
            )
            stale_current_verdict = str(line or "").lstrip().startswith(
                ("**明日裁决**", "- **明日裁决**")
            ) and any(marker in line for marker in ("只处理旧仓", "已有1x", "同股T"))
            stale_compact_action = str(line or "").lstrip().startswith(
                ("- **明天能不能开仓**:", "- 明日动作：", "- 明日动作:")
            ) and any(marker in line for marker in ("只处理旧仓", "已有1x", "同股T"))
            if stale_global_wording or stale_current_action or stale_current_verdict or stale_compact_action:
                findings.append(
                    _finding(
                        "position_inferred_rendered_as_confirmed_holding",
                        "待核实外部交易被账户动作行写成确认持仓，核实成交前必须按0x处理；停止生成",
                        line=offset,
                    )
                )
                break
            if not cells or cells[0] not in {"旧仓处理", "当前持仓", "已有旧仓", "成交确认", "外部交易核实"}:
                continue
            row_codes = _stock_codes_in_text(line)
            if not (row_codes & expected_codes):
                continue
            if not _has_pending_trade_wording(line):
                findings.append(
                    _finding(
                        "position_inferred_rendered_as_confirmed_holding",
                        "待核实外部交易被正文写成确认持仓，必须保留外部交易待核实口径；停止生成",
                        line=offset,
                    )
                )
                break
    html_assets = _extract_html_timeline_assets(companion_html)
    if html_assets:
        html_codes = _stock_codes_in_text(html_assets.get("td", ""))
        missing_html_codes = sorted(expected_codes - html_codes)
        if missing_html_codes:
            findings.append(
                _finding(
                    "position_day_order_html_current_position_missing",
                    "Bear HTML 的Td没有写出数据库旧仓对象："
                    + "、".join(missing_html_codes)
                    + "；停止生成",
                )
            )
        if inferred_position:
            td_html_text = _extract_html_timeline_row_text(companion_html, "td")
            te_html_text = _extract_html_timeline_row_text(companion_html, "te")
            te_html_markup = _extract_html_timeline_row_markup(companion_html, "te")
            te_html_identity = _target_identity(html_assets.get("te", ""))
            te_html_tracks_inferred_position = (
                not te_html_identity
                or bool(_stock_codes_in_text(html_assets.get("te", "")) & expected_codes)
            )
            if (
                not _has_pending_trade_wording(td_html_text)
                or (
                    te_html_tracks_inferred_position
                    and (
                        not _has_pending_trade_wording(te_html_text)
                        or not _has_pending_trade_b1_rule(te_html_text)
                        or not _has_pending_trade_no_b2_rule(te_html_text)
                        or (
                            inferred_verification_only
                            and (
                                "0%不参与" not in te_html_text
                                or "只核实" not in te_html_text
                            )
                        )
                    )
                )
                or bool(inferred_verification_only and te_html_tracks_inferred_position and
                    re.search(
                        r'class=["\'][^"\']*timeline-action-badge[^"\']*(?:is-participate|is-confirm)[^"\']*["\']',
                        te_html_markup,
                        re.I,
                    )
                )
                or bool(inferred_verification_only and te_html_tracks_inferred_position and
                    re.search(
                        r'class=["\'][^"\']*timeline-date-intent[^"\']*(?:is-buy|is-confirm)[^"\']*["\']',
                        str(companion_html or ""),
                        re.I,
                    )
                )
                or any(
                    marker in f"{td_html_text} {te_html_text}"
                    for marker in inferred_confirmed_markers
                )
            ):
                findings.append(
                    _finding(
                        "position_day_order_html_inferred_confirmation_missing",
                        "Bear HTML 没有保留外部交易待核实口径；停止生成",
                    )
                )
    return findings


def _audit_position_day_order_history_paths(
    lines,
    source_path=None,
    *,
    prefer_postgres_history=False,
):
    if source_path is None:
        if _extract_day_order_rows(lines):
            return [
                _finding(
                    "position_day_order_history_source_path_missing",
                    "账户日序历史校验需要报告路径，程序化调用必须传入 source_path",
                )
            ]
        return []
    if _read_day_order_account_state is None or _day_order_target_label is None:
        return []
    output_root = Path(source_path).parent
    findings = []
    for offset, cells in _extract_day_order_rows(lines):
        code = cells[0]
        if code not in {"Ta", "Tb", "Tc"}:
            continue
        row_date = _day_order_date(cells[1])
        if not row_date:
            continue
        expected_state = _read_day_order_account_state(
            row_date,
            output_root=output_root,
            prefer_postgres_history=prefer_postgres_history,
        )
        expected_state_name = expected_state.get("state")
        expected = (
            expected_state.get("target")
            if expected_state_name in {"target", "inferred"}
            else {}
        )
        expected_label = _day_order_target_label(expected) if expected else ""
        visible_text = f"{cells[2]} {cells[3]}"
        visible_identity = _target_identity(cells[3])
        if not visible_identity:
            code_match = re.search(r"(?<!\d)(\d{6})(?!\d)", visible_text)
            visible_identity = code_match.group(1) if code_match else ""
        if not visible_identity and re.search(r"[：:]", cells[2]):
            account_prefix, account_value = re.split(r"[：:]", cells[2], maxsplit=1)
            account_value = account_value.rsplit("：", 1)[-1].rsplit(":", 1)[-1].strip()
            unknown_values = {"", "-", "无", "空仓", "持仓未输入"}
            if (
                any(marker in account_prefix for marker in ("路径", "复盘日", "交易日", "持仓", "旧仓"))
                and account_value not in unknown_values
                and "持仓未输入" not in account_value
                and not any(marker in account_value for marker in ("待确认", "事实待确认", "无旧仓"))
            ):
                visible_identity = account_value
        if expected_label and expected_label not in visible_text:
            findings.append(
                _finding(
                    "position_day_order_history_path_missing",
                    f"{code} 对应 {row_date} 的历史路径是 {expected_label}，账户日序不能写成空仓或缺失路径",
                    line=offset,
                )
            )
        elif expected_state_name == "inferred":
            pending_text = " ".join(cells[2:6])
            confirmed_markers = (
                "历史持仓",
                "可能形成B1旧仓",
                "已有旧仓",
                "旧仓进入复核",
            )
            if not _has_pending_trade_wording(pending_text) or any(
                marker in pending_text for marker in confirmed_markers
            ):
                findings.append(
                    _finding(
                        "position_day_order_history_inferred_confirmation_missing",
                        f"{code} 对应 {row_date} 是外部交易待核实路径，不能写成确认持仓",
                        line=offset,
                    )
                )
        elif expected_state_name == "empty" and visible_identity:
            findings.append(
                _finding(
                    "position_day_order_history_empty_conflict",
                    f"{code} 对应 {row_date} 的账户日是空仓，账户日序不能写成 {visible_text.strip()}",
                    line=offset,
                )
            )
        elif expected_state_name == "unknown" and visible_identity:
            findings.append(
                _finding(
                    "position_day_order_history_unknown_conflict",
                    f"{code} 对应 {row_date} 的账户事实未确认，账户日序不能写成确定股票 {visible_text.strip()}",
                    line=offset,
                )
            )
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
    if not labels.intersection({"明日仓位", "明日新仓"}):
        findings.append(
            _finding(
                "account_advice_missing_position",
                "明日账户建议必须写明日新仓，不能只写观察动作",
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


def _audit_position_action_semantics(lines):
    section = _front_account_section_with_offsets(lines)
    if not section:
        return []

    rows = []
    for offset, line in section:
        cells = _split_md_row(line)
        if len(cells) >= 2 and not _is_separator_cells(cells):
            rows.append((offset, cells[0], cells[1]))

    def matching_rows(*labels):
        wanted = set(labels)
        return [(offset, value) for offset, label, value in rows if label in wanted]

    fact_rows = matching_rows("旧仓事实")
    fact_text = " ".join(str(value or "") for _, value in fact_rows)
    action_rows = matching_rows("旧仓动作")
    judgment_rows = matching_rows("旧仓判断")
    tomorrow_result_rows = matching_rows("明日账户结果")
    explicit_tomorrow_empty = any(
        str(value or "").strip() == "明日空仓"
        for _, value in tomorrow_result_rows
    )
    findings = []

    if explicit_tomorrow_empty:
        new_entry_text = " ".join(str(value or "") for _, value in matching_rows("明日新仓"))
        action_text = " ".join(str(value or "") for _, value in action_rows)
        closing_text = " ".join(str(value or "") for _, value in matching_rows("收盘目标仓位"))
        complete = bool(
            ("0%" in new_entry_text or "不买新股" in new_entry_text)
            and all(
                marker in action_text
                for marker in (
                    "不买新股",
                    "不做T",
                    "集合竞价",
                    "卖清全部可卖旧仓",
                    "继续尽早卖",
                    "未清完不能称空仓",
                )
            )
            and closing_text.startswith("0%")
            and "未清完不能称空仓" in closing_text
        )
        if not complete:
            findings.append(
                _finding(
                    "tomorrow_empty_action_incomplete",
                    "明日空仓必须同时写清不买新股、集合竞价卖清全部可卖旧仓、不做T、卖清后仓位0，以及未清完继续尽早卖且不能称空仓",
                    line=tomorrow_result_rows[0][0],
                )
            )

    if "持仓未输入" in fact_text:
        for offset, value in matching_rows("账户风险暴露", "收盘目标仓位"):
            text = str(value or "").strip()
            if re.search(r"(?<![\w.])0x(?!\w)", text, flags=re.I) or text.startswith("0%"):
                findings.append(
                    _finding(
                        "unknown_position_exposure_zero",
                        "持仓未输入时，账户风险暴露和收盘目标仓位必须写待确认，不能写成0x或0%",
                        line=offset,
                    )
                )
                break

    if "已确认无旧仓" in fact_text and not explicit_tomorrow_empty:
        current_action_labels = {
            "明天是否参与",
            "明天能不能开仓",
            "明日大盘预期",
            "明日环境与跟随裁决",
            "市场情绪状态",
            "明日策略",
        }
        current_action_prefixes = (
            "**明日裁决**:",
            "**裁决依据**:",
            "**开盘前动作**:",
            "- **明日裁决**:",
            "- **明天能不能开仓**:",
            "- **明天具体怎么做**:",
            "- 候选观察样本对象是否继续走强；",
            "- 以观察和处理持仓为主",
        )
        conflict_markers = ("只处理旧仓", "若你有旧仓", "若有旧仓", "先退出")
        for index, line in enumerate(lines, 1):
            text = str(line or "").strip()
            cells = _split_md_row(text)
            is_current_action = bool(cells and cells[0] in current_action_labels) or text.startswith(
                current_action_prefixes
            )
            if not is_current_action or not any(marker in text for marker in conflict_markers):
                continue
            findings.append(
                _finding(
                    "explicit_empty_old_position_action_conflict",
                    "已确认无旧仓时，当前动作不能再写处理旧仓或先退出",
                    line=index,
                )
            )
            break

    confirmed = "已确认持有" in fact_text
    if confirmed:
        action_markers = (
            "09:50-10:10",
            "14:30-14:55",
            "按原持有预案",
            "先补持仓周期",
            "先核对实际持仓",
            "集合竞价卖清",
        )
        if not action_rows or not any(
            any(marker in str(value or "") for marker in action_markers)
            for _, value in action_rows
        ):
            findings.append(
                _finding(
                    "confirmed_old_position_action_missing",
                    "已确认旧仓必须给出独立旧仓动作，不能只写明日不新增参与",
                    line=fact_rows[0][0] if fact_rows else section[0][0],
                )
            )

    pending = _has_pending_trade_wording(fact_text)
    if pending and not explicit_tomorrow_empty:
        negative_sell_markers = ("不卖", "不执行持仓卖出", "不得卖出", "不能卖出")
        sell_action_markers = ("完成退出", "退出旧仓", "卖出旧仓", "尾盘卖出", "先卖", "清仓")
        pending_action_rows = matching_rows("旧仓动作", "账户先处理", "明日动作", "旧仓处理")
        for offset, value in pending_action_rows:
            text = str(value or "")
            for marker in negative_sell_markers:
                text = text.replace(marker, "")
            if any(marker in text for marker in sell_action_markers):
                findings.append(
                    _finding(
                        "pending_position_sell_action_conflict",
                        "外部交易待核实时只核实成交记录，核实成交前不能生成旧仓卖出动作",
                        line=offset,
                    )
                )
                break

    failed_rows = [
        (offset, value)
        for offset, value in judgment_rows
        if "已经失败" in str(value or "")
    ]
    if failed_rows and not explicit_tomorrow_empty:
        def completes_morning_exit(value):
            text = str(value or "")
            if "09:50-10:10" not in text:
                return False
            if any(
                marker in text
                for marker in ("不退出", "不卖", "不清仓", "暂不退出", "只观察", "仅观察", "只复核", "仅复核")
            ):
                return False
            return any(
                marker in text
                for marker in ("完成退出", "退出旧仓", "卖出旧仓", "卖出", "清仓")
            )

        if not action_rows or not any(completes_morning_exit(value) for _, value in action_rows):
            findings.append(
                _finding(
                    "morning_exit_window_missing",
                    "已经失败的旧仓必须写明在09:50-10:10完成退出",
                    line=failed_rows[0][0],
                )
            )

    return findings


def _extract_html_account_action_values(companion_html):
    text = str(companion_html or "")
    heading_pattern = re.compile(r"<h[1-6]\b[^>]*>(.*?)</h[1-6]>", re.I | re.S)
    for heading_match in heading_pattern.finditer(text):
        if _clean_html_cell(heading_match.group(1)) != "明日账户建议":
            continue
        section_tail = text[heading_match.end() :]
        next_heading = heading_pattern.search(section_tail)
        if next_heading:
            section_tail = section_tail[: next_heading.start()]
        table_match = re.search(r"<table\b[^>]*>(.*?)</table>", section_tail, re.I | re.S)
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
    return None


def _audit_position_action_html_semantics(
    lines,
    companion_html,
    *,
    require_html_account_action=False,
):
    section = _front_account_section_with_offsets(lines)
    if not section:
        return []
    rows = []
    for offset, line in section:
        cells = _split_md_row(line)
        if len(cells) >= 2 and not _is_separator_cells(cells):
            rows.append((offset, cells[0], cells[1]))
    tomorrow_result_rows = [
        (offset, value)
        for offset, label, value in rows
        if label == "明日账户结果" and str(value or "").strip() == "明日空仓"
    ]
    if not tomorrow_result_rows:
        return []

    values = _extract_html_account_action_values(companion_html)
    if values is None:
        if not require_html_account_action:
            return []
        return [
            _finding(
                "tomorrow_empty_html_action_missing",
                "Bear HTML 必须显示明日账户建议及完整明日空仓动作",
                line=tomorrow_result_rows[0][0],
            )
        ]

    new_entry_text = str(values.get("明日新仓") or "")
    action_text = str(values.get("旧仓动作") or "")
    closing_text = str(values.get("收盘目标仓位") or "")
    complete = bool(
        str(values.get("明日账户结果") or "").strip() == "明日空仓"
        and ("0%" in new_entry_text or "不买新股" in new_entry_text)
        and all(
            marker in action_text
            for marker in (
                "不买新股",
                "不做T",
                "集合竞价",
                "卖清全部可卖旧仓",
                "继续尽早卖",
                "未清完不能称空仓",
            )
        )
        and closing_text.startswith("0%")
        and "未清完不能称空仓" in closing_text
    )
    if complete:
        return []
    return [
        _finding(
            "tomorrow_empty_html_action_incomplete",
            "Bear HTML 的明日空仓必须写清不买新股、集合竞价卖清全部可卖旧仓、不做T、卖清后仓位0，以及未清完继续尽早卖且不能称空仓",
            line=tomorrow_result_rows[0][0],
        )
    ]


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
    action_text = str(text or "")
    for marker in sorted(ZERO_POSITION_ALLOWED_PARTICIPATION_MARKERS, key=len, reverse=True):
        action_text = action_text.replace(marker, "")
    return any(marker in action_text for marker in ZERO_POSITION_POSITIVE_PARTICIPATION_MARKERS)


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
    if _final_summary_has_conditional_zero_plan(front):
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

    def _has_positive_mainline_core_identity(cells):
        for cell in cells:
            text = str(cell or "").strip()
            if not text or "主线核心" not in text:
                continue
            if text in {"主线核心", "主线核心候选"} or text.startswith("主线核心"):
                return True
            if re.search(r"(?:身份|来源池|对象口径|角色)[:：]\s*主线核心", text):
                return True
            negative_context = re.search(r"(?:不是|非|不标|不能|无确认|为0|缺少).{0,12}主线核心", text)
            if negative_context:
                continue
            if re.search(r"(?:^|[；;|])\s*主线核心(?:$|[；;/、，,])", text):
                return True
        return False

    findings = []
    for index, line in enumerate(lines, 1):
        cells = _split_md_row(line)
        if not cells or _is_separator_cells(cells):
            continue
        if not _has_positive_mainline_core_identity(cells):
            continue
        row_text = " ".join(cells)
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
                    f"Top50成交额占比趋势必须包含报告日{target_date}，当前范围为{row_dates[0]}到{row_dates[-1]}",
                )
            )
        if len(row_dates) < 25:
            findings.append(
                _finding(
                    "top50_recent_window_incomplete",
                    f"Top50成交额占比趋势必须展示近25个交易日，当前只有{len(row_dates)}行",
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
                    "创新高趋势反馈不能用旧因子日替代报告日",
                )
            )
        has_target_row = any(str(line).startswith(f"| {target_date} |") for line in new_high_section)
        if not has_target_row:
            findings.append(
                _finding(
                    "new_high_target_date_missing",
                    f"创新高趋势反馈必须包含报告日行：{target_date}",
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
    has_heading = (
        EXTREME_CONVICTION_TRACKING_HEADING in text
        or EXTREME_CONVICTION_TRACKING_HISTORICAL_HEADING in text
    )
    if not has_heading or EXTREME_CONVICTION_TRACKING_HEADER not in lines:
        return [
            _finding(
                "extreme_conviction_tracking_missing",
                "报告必须用结构化台账展示历史明日极度看好近25日跟踪表",
            )
        ]
    findings = []
    rows = _extract_table_rows_after_header(lines, EXTREME_CONVICTION_TRACKING_HEADER)
    if not rows:
        findings.append(
            _finding(
                "extreme_conviction_tracking_empty",
                "明日极度看好近25日跟踪表必须至少包含一条结构化样本",
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
                    f"首页不能暴露推导链标记：{marker}",
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
                "推导展示缺少必要行：" + ", ".join(missing),
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
                    f"首页不能使用模拟或噪声表述：{marker}",
                )
        theory_action_found = False
        for marker in THEORY_ACTION_MARKERS:
            if marker in text:
                theory_action_found = True
                append_theory_finding(
                    "theory_driven_action_language",
                    f"首页不能用理论概念直接解释动作原因：{marker}",
                )
        if not theory_action_found and _has_theory_action_context(text):
            append_theory_finding(
                "theory_driven_action_language",
                "首页不能用理论概念直接解释动作、资格或仓位变化",
            )
        for marker in THEORY_NOISE_MARKERS:
            if marker in text:
                append_theory_finding(
                    "theory_noise_language",
                    f"首页不能使用理论或噪声表述：{marker}",
                )
        for term in THEORY_CONCEPT_TERMS:
            if term in text:
                append_theory_finding(
                    "theory_noise_language",
                    f"首页不能使用未落到字段里的理论概念：{term}",
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
                    "报告仍使用已停用的日报表述",
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


PREMARKET_FIXED_DECISION_LEGACY_MARKERS = (
    "盘前0%；参与窗口" + "命中后才评估50%条件执行",
    "盘前0%；观察窗口命中后才评估50%条件执行",
    "盘前0%；固定交易窗口内条件成立后才评估50%条件执行",
    "盘前0%；固定交易窗口条件满足后才评估50%条件执行",
    "条件成立才评估50%条件执行",
    "条件满足才50%条件执行",
    "命中固定交易窗口条件才评估50%条件执行",
    "固定交易窗口内条件成立后才评估50%条件执行",
    "固定交易窗口条件成立才参与",
    "固定交易窗口条件成立才50%条件执行",
    "观察对象重新成立",
)
POSITIVE_PREMARKET_UNDECIDED_ACTION_MARKERS = (
    "条件满足才新开",
    "命中才新开",
    "买入区间命中才",
    "再决定是否进入50%",
    "再评估50%",
    "才评估50%",
)
POSITIVE_PREMARKET_DECIDED_MARKERS = (
    "已决定",
    "昨晚预案",
    "昨晚1x/50%半仓预案",
    "昨晚2x/100%满仓预案",
)
POSITIVE_PREMARKET_TWO_B_MARKERS = ("B1", "B2")
POSITIVE_PREMARKET_TWO_B_CANCEL_MARKERS = ("取消B2", "不补B2", "B1未变强", "走弱先取消")
POSITIVE_PREMARKET_B1_ONLY_LIMIT_MARKERS = (
    "本计划无B2",
    "不追加B2",
    "1x是本计划仓位上限",
    "1x/50%为本计划上限",
)
ONE_SHOT_BUY_WORDING_MARKERS = (
    "必须买够",
    "一次买满",
    "一次买齐",
    "开盘一次买满",
    "补足任务仓",
    "必须补足",
)
LEGACY_TIMELINE_QUALIFICATION_MARKERS = (
    "Tb/Tc资格",
    "单独看Tb/Tc",
    "新仓是否叠加单独看Tb/Tc",
)
LEGACY_EXECUTION_OBJECT_SURFACE_MARKERS = (
    "已进入明日执行对象",
)


def _has_two_b_cancellation_language(text):
    value = str(text or "")
    return (
        all(marker in value for marker in POSITIVE_PREMARKET_TWO_B_MARKERS)
        and any(marker in value for marker in POSITIVE_PREMARKET_TWO_B_CANCEL_MARKERS)
    )


def _has_b1_only_limit_language(text):
    value = str(text or "")
    return "B1" in value and any(marker in value for marker in POSITIVE_PREMARKET_B1_ONLY_LIMIT_MARKERS)


def _audit_premarket_fixed_decision_language(lines):
    findings = []
    for offset, line in enumerate(lines, 1):
        text = str(line or "")
        for marker in PREMARKET_FIXED_DECISION_LEGACY_MARKERS:
            if marker not in text:
                continue
            findings.append(
                _finding(
                    "premarket_fixed_decision_legacy_wording",
                    "明天买卖决定必须在当晚日报里完成；盘中条件只能执行或取消既定预案，不能把观察对象临时升级成买入对象",
                    line=offset,
                )
            )
            break
    return findings


POSITION_TIER_INVALID_SURFACE_MARKERS = (
    "25%试仓",
    "25% 试仓",
    "10%机动仓",
    "50%底仓",
    "50%机动仓",
)


def _audit_position_tier_visible_language(lines):
    front = _front_page_lines(lines)
    if not front:
        return []
    findings = []
    section_values = {}
    section_offsets = {}
    for offset, line in enumerate(front, 1):
        cells = _split_md_row(line)
        if len(cells) >= 2 and not _is_separator_cells(cells):
            label = cells[0]
            if label in MONTHLY_RHYTHM_REQUIRED_LABELS:
                section_values[label] = cells[1]
                section_offsets[label] = offset

    attack_grade = section_values.get("进攻仓位三态")
    max_position_text = section_values.get("明日最大仓位")
    max_position = _parse_percent_int(max_position_text)
    expected_max_position = {"0%": 0, "50%": 50, "100%": 100}.get(attack_grade)
    if expected_max_position is not None and max_position is not None and max_position != expected_max_position:
        findings.append(
            _finding(
                "position_tier_semantic_conflict",
                f"进攻仓位是{attack_grade}时，明日最大仓位必须同为{expected_max_position}%",
                line=section_offsets.get("明日最大仓位") or section_offsets.get("进攻仓位三态"),
            )
        )

    for offset, line in enumerate(front, 1):
        text = str(line or "")
        conflict = ""
        if "满仓条件执行" in text and (
            attack_grade == "50%"
            or any(marker in text for marker in ("50%", "仓位=50", "position_pct': 50", 'position_pct": 50'))
        ):
            conflict = "同一动作不能同时写50%条件执行和满仓"
        elif re.search(
            r"(?:1x\s*[/=：为]\s*100%|100%\s*[/=：为]\s*1x|1x\s*(?:是|为)?\s*满仓)",
            text,
            flags=re.IGNORECASE,
        ):
            conflict = "1x只能对应50%半仓，不能对应100%"
        elif re.search(r"(?:2x\s*[/=：为]\s*200%|200%\s*[/=：为]\s*2x)", text, flags=re.IGNORECASE):
            conflict = "2x只能对应100%满仓，不能对应200%"
        elif any(marker in text for marker in POSITION_TIER_INVALID_SURFACE_MARKERS):
            conflict = "仓位只使用0、1x/50%和2x/100%三档，不能出现额外分仓档"
        elif attack_grade == "50%" and any(
            marker in text
            for marker in (
                "B2只在确认后补到2x/100%",
                "B2确认后补到2x/100%",
                "B2再补到2x/100%",
                "加B2至2x/100%",
            )
        ) and not any(marker in text for marker in ("同股T", "旧仓1x/50% + 新仓1x/50%")):
            conflict = "1x/50%计划只执行B1，不能把B2写成普通追加动作"
        if conflict:
            findings.append(
                _finding(
                    "position_tier_semantic_conflict",
                    conflict,
                    line=offset,
                )
            )
    return findings


def _audit_market_snapshot_risk_consistency(lines):
    full_text = "\n".join(str(line or "") for line in list(lines or []))
    if "风险点**: 暂无明确风险" not in full_text and "风险点 | 暂无明确风险" not in full_text:
        return []
    risky_markers = (
        "跌停12",
        "跌停 12",
        "涨跌比 1434 / 4034",
        "震荡偏风险",
        "收缩防守",
        "下跌家数偏多",
    )
    if not any(marker in full_text for marker in risky_markers):
        return []
    findings = []
    for offset, line in enumerate(lines, 1):
        text = str(line or "")
        if "风险点**: 暂无明确风险" in text or "风险点 | 暂无明确风险" in text:
            findings.append(
                _finding(
                    "market_snapshot_risk_conflict",
                    "市场已显示跌多涨少或收缩防守时，市场快照不能写暂无明确风险",
                    line=offset,
                )
            )
    return findings


def _audit_sector_fund_flow_visible_zero_tables(lines):
    findings = []
    for heading in ("### 资金流入TOP10", "### 资金流出结果"):
        rows = _table_rows_after_heading(lines, heading)
        data_rows = [row for row in rows if len(row) >= 4 and row[0] != "排名"]
        if len(data_rows) < 3:
            continue
        named_rows = [row for row in data_rows if row[1] and row[1] not in {"-", "暂无", "无"}]
        if len(named_rows) < 3:
            continue
        numeric_pairs = [
            (_parse_visible_number(row[2]), _parse_visible_number(row[3]))
            for row in named_rows
        ]
        numeric_pairs = [pair for pair in numeric_pairs if pair[0] is not None and pair[1] is not None]
        if len(numeric_pairs) < 3:
            continue
        if all(abs(net_flow) < 0.0001 and abs(change_pct) < 0.0001 for net_flow, change_pct in numeric_pairs):
            findings.append(
                _finding(
                    "sector_fund_flow_visible_all_zero",
                    f"{heading} 有有效板块名称，但净流入/净流出和涨跌幅整表为0；需检查行业资金字段是否已正确归一",
                )
            )
    return findings


def _audit_positive_premarket_fixed_decision_language(lines):
    front = _front_page_lines(lines)
    participation_pct = _positive_participation_pct(front)
    if participation_pct < 50:
        return []

    findings = []
    section = _front_account_section_with_offsets(lines)
    target_lines = section or list(enumerate(front, 1))
    for offset, line in target_lines:
        text = str(line or "")
        if any(marker in text for marker in POSITIVE_PREMARKET_UNDECIDED_ACTION_MARKERS):
            findings.append(
                _finding(
                    "positive_premarket_action_undecided_wording",
                    "1x/50%或2x/100%计划必须在当晚决定；1x只执行B1，2x才允许确认后执行B2；不满足取消或回到0%",
                    line=offset,
                )
            )

    if section:
        rows = []
        for offset, line in section:
            cells = _split_md_row(line)
            if len(cells) >= 2 and not _is_separator_cells(cells):
                rows.append((offset, cells[0], cells[1]))
        key_text = "\n".join(
            str(value or "")
            for _, label, value in rows
            if label in ("明日动作", "价格条件", "明日仓位", "明日新仓")
        )
        if key_text and not any(marker in key_text for marker in POSITIVE_PREMARKET_DECIDED_MARKERS):
            findings.append(
                _finding(
                    "positive_premarket_action_missing_decided_wording",
                    "1x/50%或2x/100%计划必须表达为当晚已决定的执行计划；不满足取消或回到0%",
                    line=section[0][0],
                )
            )
        if participation_pct == 50 and key_text and not _has_b1_only_limit_language(key_text):
            findings.append(
                _finding(
                    "positive_premarket_action_position_tier_mismatch",
                    "1x/50%计划必须写清只执行B1，且本计划不追加B2",
                    line=section[0][0],
                )
            )
        if participation_pct >= 100 and key_text and not _has_two_b_cancellation_language(key_text):
            findings.append(
                _finding(
                    "positive_premarket_action_position_tier_mismatch",
                    "2x/100%计划必须写清B1参与、B2确认及未确认时取消B2",
                    line=section[0][0],
                )
            )
    return findings


def _audit_one_shot_buy_wording(lines):
    findings = []
    for offset, line in enumerate(lines, 1):
        text = str(line or "")
        for marker in ONE_SHOT_BUY_WORDING_MARKERS:
            if marker not in text:
                continue
            findings.append(
                _finding(
                    "one_shot_buy_wording",
                    f"日报不能出现会诱导一次买满或把B2当任务的表达：{marker}",
                    line=offset,
                )
            )
            break
    return findings


def _audit_legacy_timeline_qualification_wording(lines):
    findings = []
    for offset, line in enumerate(lines, 1):
        text = str(line or "")
        for marker in LEGACY_TIMELINE_QUALIFICATION_MARKERS:
            if marker not in text:
                continue
            findings.append(
                _finding(
                    "legacy_timeline_qualification_wording",
                    "账户日序已迁移为Ta-Te：明日执行资格必须写Te执行资格，不能继续写Tb/Tc资格",
                    line=offset,
                )
            )
            break
    return findings


def _audit_legacy_execution_object_surface_wording(lines):
    findings = []
    for offset, line in enumerate(lines, 1):
        text = str(line or "")
        for marker in LEGACY_EXECUTION_OBJECT_SURFACE_MARKERS:
            if marker not in text:
                continue
            findings.append(
                _finding(
                    "legacy_execution_object_surface_wording",
                    "明日对象表达必须写清B1/B2执行计划，不能只写已进入明日执行对象",
                    line=offset,
                )
            )
            break
    return findings


def _positive_participation_pct(lines):
    text = "\n".join(str(line or "") for line in list(lines or []))
    if any(marker in text for marker in ("100%核心进攻", "100%核心进攻", "条件100%核心进攻")):
        return 100
    if "满仓条件执行" in text:
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
    if not _has_stock_reference(cells):
        return False
    if len(cells) >= 2 and cells[0] in ZERO_POSITION_CURRENT_DECISION_ACTION_LABELS and not _is_empty_target(cells[1]):
        return True
    action_text = row_text
    for marker in sorted(ZERO_POSITION_NO_ACTION_ROW_MARKERS, key=len, reverse=True):
        action_text = action_text.replace(marker, "")
    return any(marker in action_text for marker in ZERO_POSITION_ACTION_MARKERS)


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
                "最终结论为0%不参与，但首页明日动作仍写了具体参与对象",
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
                        "最终结论为0%不参与，但当前决策面板仍写了主参与对象或补位参与对象",
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
                    "最终结论为0%不参与，但报告仍保留旧版明日动作表述",
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
                "最终结论为0%不参与，但伴随HTML缺少明日抉择",
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
            "最终结论为0%不参与，但伴随HTML明日抉择未同步为0%不参与",
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
                "最终摘要必须展示0/50/100仓位状态，不再使用旧版空仓/短线/30%样式",
            )
        ]
    if not any(marker in style for marker in POSITION_STYLE_GRADE_MARKERS):
        return [
            _finding(
                "position_style_missing_grade",
                "最终摘要执行风格必须包含0/50/100仓位状态",
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
        "空仓",
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
        or "空仓" in text
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
    required_labels = ("明日仓位", "执行目标", "不参与依据", "无执行目标原因", "责任归因")
    label_aliases = {
        "明日仓位": ("明日新仓", "明日仓位"),
        "执行目标": ("执行目标", "明日执行对象"),
    }
    values = {}
    offsets = {}
    for label in required_labels:
        value, offset = "", None
        for candidate_label in label_aliases.get(label, (label,)):
            value, offset = _extract_front_kv_value(front, candidate_label)
            if str(value or "").strip():
                break
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
                f"首页执行对象 {front_object} 与审计层对象 {audit_object} 不一致",
            )
        ]
    return []


def _audit_b_level_conditions(lines):
    front_text = "\n".join(str(line or "") for line in _front_page_lines(lines))
    has_condition_heading = "## 50%条件执行条件" in front_text or "## 满仓条件执行条件" in front_text
    if not has_condition_heading:
        has_execution_conclusion = "## 明日执行结论" in front_text and "| 明日执行对象 |" in front_text
        execution_object_is_none = "| 明日执行对象 | 无 |" in front_text
        if not (
            has_execution_conclusion
            and not execution_object_is_none
            and ("50%条件执行" in front_text or "满仓条件执行" in front_text)
        ):
            return []
    if "低开承接型" in front_text and "主动进攻型" in front_text:
        return []
    return [
        _finding(
            "b_level_conditions_missing",
            "首页提到50%条件执行，但没有同时展示50%执行触发条件",
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
                "前台已经给出明日执行对象，但后文又否定同一对象",
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
                "前台已经给出明日执行对象，但后文又把同一对象降为只观察",
                line=offset,
            )
        )
    return findings


def _limit_down_text_is_negated(text):
    return any(marker in text for marker in ("未跌停", "非跌停", "不跌停", "没有跌停", "并非跌停"))


def _line_has_limit_down_fact(line):
    text = str(line or "")
    if "跌停" in text and not _limit_down_text_is_negated(text):
        return True
    for match in re.finditer(r"([+-]?\d+(?:\.\d+)?)%", text):
        try:
            if float(match.group(1)) <= -9.5:
                return True
        except ValueError:
            continue
    return False


def _has_explicit_limit_down_reversal_text(text):
    text = str(text or "")
    return any(marker in text for marker in LIMIT_DOWN_REVERSAL_PLAN_MARKERS)


def _line_text_before_process_evidence_final_action_tail(text):
    text = str(text or "")
    tail_markers = (
        "（过程证据，不覆盖唯一明日动作",
        "(过程证据，不覆盖唯一明日动作",
        "过程证据，不覆盖唯一明日动作",
    )
    indexes = [text.find(marker) for marker in tail_markers if marker in text]
    if not indexes:
        return text
    return text[: min(indexes)]


def _line_target_fact_segments(text, front_identity="", target_name=""):
    text = str(text or "")
    if "|" in text:
        return [text]
    segments = re.split(r"[；;。.!！?？\n]", text)
    return [
        segment
        for segment in segments
        if (front_identity and front_identity in segment) or (target_name and target_name in segment)
    ]


def _front_has_explicit_limit_down_reversal_plan(front_lines, front_identity="", target_name=""):
    target_lines = []
    action_lines = []
    for line in front_lines or []:
        text = str(line or "")
        if (front_identity and front_identity in text) or (target_name and target_name in text):
            target_lines.append(text)
            continue
        if any(marker in text for marker in ("明日动作", "仓位姿态", "执行性质", "执行条件", "不参与条件")):
            action_lines.append(text)
    text = "\n".join(target_lines + action_lines)
    has_reversal = _has_explicit_limit_down_reversal_text(text)
    if not has_reversal:
        return False
    has_window = any(window in text for window in REQUIRED_EXECUTION_WINDOWS) or "09:" in text or "09：" in text
    has_invalid = any(marker in text for marker in ("作废", "取消", "失效", "认错线", "跌破", "站不回", "封死", "打不开"))
    has_zero_fallback = "回到0%" in text or "0%不参与" in text or ("0%" in text and "不参与" in text)
    return bool(has_window and has_invalid and has_zero_fallback)


def _audit_front_execution_object_limit_down_without_reversal_plan(lines):
    front = _front_page_lines(lines)
    front_object = _extract_front_execution_object(lines)
    front_identity = _target_identity(front_object)
    if not front_identity or _is_empty_target(front_object):
        return []
    target_text = _target_text_without_role(front_object)
    target_name = re.sub(r"[\(（]?\d{6}[\)）]?", "", target_text).strip()
    if _front_has_explicit_limit_down_reversal_plan(front, front_identity=front_identity, target_name=target_name):
        return []
    for offset, line in enumerate(lines, 1):
        text = str(line or "")
        subject_text = _line_text_before_process_evidence_final_action_tail(text)
        if front_identity not in subject_text and not (target_name and target_name in subject_text):
            continue
        fact_segments = _line_target_fact_segments(
            subject_text,
            front_identity=front_identity,
            target_name=target_name,
        )
        if not any(_line_has_limit_down_fact(segment) for segment in fact_segments):
            continue
        return [
            _finding(
                "front_execution_object_limit_down_without_reversal_plan",
                "前台已经给出明日执行对象，但同一报告又写成跌停/接近跌停，且没有明确跌停反包专项计划",
                line=offset,
            )
        ]
    return []


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
                f"T-006当前核心候选 {candidate} 与最终对象 {detail} 不一致",
                line=offset,
            )
        )

    if _final_summary_is_zero_position(_front_page_lines(lines)):
        findings.append(
            _finding(
                "daily_judgment_core_candidate_without_execution",
                f"T-006当前核心候选 {candidate} 是具体股票，但最终结果没有执行对象",
                line=offset,
            )
        )
    return findings


def _audit_daily_judgment_settled_fact_visibility(lines):
    findings = []
    in_settled_block = False
    for offset, line in enumerate(lines, 1):
        text = str(line or "").strip()
        if text.startswith("**近") and "已结算交易日复盘表现" in text:
            in_settled_block = True
            continue
        if text.startswith("**结算上一交易日"):
            in_settled_block = True
            continue
        if text.startswith("**上一交易日未完成结算") or text.startswith("**今日判断"):
            in_settled_block = False
            continue
        if not in_settled_block:
            continue
        cells = _split_md_row(line)
        if len(cells) < 2 or _is_separator_cells(cells) or cells[0] == "判断项" or cells[0] == "暂无已结算项":
            continue
        if "待补事实" in " ".join(cells):
            findings.append(
                _finding(
                    "daily_judgment_settled_table_unresolved_fact",
                    "已结算复盘表不能把待补事实作为结论输出，应放到未完成结算区",
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
                "过程候选替换原因必须说明同池对比维度，不能只重复未入选",
                line=offset,
            )
        )
    return findings


def _extract_bayesian_front_section(lines):
    section = []
    found = False
    for offset, line in enumerate(lines, 1):
        text = str(line or "")
        stripped = text.strip()
        if not found:
            if stripped == BAYESIAN_FRONT_HEADING:
                found = True
            continue
        if text.startswith("## ") or text.startswith("### "):
            break
        section.append((offset, text))
    return found, section


def _extract_bayesian_appendix_blocks(lines):
    blocks = []
    in_code = False
    current = []
    for offset, line in enumerate(lines, 1):
        text = str(line or "")
        stripped = text.strip()
        if stripped == "```text":
            in_code = True
            current = []
            continue
        if in_code and stripped == "```":
            if any(BAYESIAN_APPENDIX_MARKER in item for _, item in current):
                blocks.append(current)
            in_code = False
            current = []
            continue
        if in_code:
            current.append((offset, text))
    return blocks


def _bayesian_table_values(section):
    values = {}
    offsets = {}
    for offset, text in section:
        cells = _split_md_row(text)
        if len(cells) < 2 or _is_separator_cells(cells):
            continue
        values[cells[0]] = cells[1]
        offsets[cells[0]] = offset
    return values, offsets


def _audit_bayesian_diagnosis_contract(lines):
    found_front, front_section = _extract_bayesian_front_section(lines)
    appendix_blocks = _extract_bayesian_appendix_blocks(lines)
    if not found_front and not appendix_blocks:
        return []
    findings = []
    scan_lines = list(front_section)
    for block in appendix_blocks:
        scan_lines.extend(block)
    for offset, text in scan_lines:
        if PROBABILITY_BAND_RE.search(text) or COARSE_PROBABILITY_LABEL_RE.search(text):
            findings.append(
                _finding(
                    "bayesian_probability_band_forbidden",
                    "路径诊断不能使用粗胜率、粗概率或粗可信标签；应使用路径结论和反证说明",
                    line=offset,
                )
            )
        if BAYESIAN_SOURCE_DATE_MISSING in text or "日期=-" in text:
            findings.append(
                _finding(
                    "bayesian_path_source_date_missing",
                    "路径诊断存在来源日期缺失，不能静默当作目标日期事实",
                    line=offset,
                )
            )
    front_values, front_offsets = _bayesian_table_values(front_section)
    path_conclusion = front_values.get("路径结论", "")
    final_alignment = front_values.get("最终动作一致性", "")
    diagnosis_target = front_values.get("执行对象", "")
    if path_conclusion == "路径一致":
        has_counter_heading = any("#### 关键反证" in text for _, text in front_section)
        has_counter_text = any("存在反证" in text and "暂无强反证" not in text for _, text in scan_lines)
        if has_counter_heading or has_counter_text:
            findings.append(
                _finding(
                    "bayesian_path_conclusion_conflicts_with_counter_evidence",
                    "路径结论写成路径一致时，不能同时展示强反证",
                    line=front_offsets.get("路径结论"),
                )
            )
    front = _front_page_lines(lines)
    final_target = _extract_final_unique_target(front)
    final_identity = _target_identity(final_target)
    diagnosis_identity = _target_identity(diagnosis_target)
    if final_identity and diagnosis_identity and final_identity != diagnosis_identity and final_alignment != "不一致":
        findings.append(
            _finding(
                "bayesian_final_object_conflict_hidden",
                "路径诊断对象与最终对象不一致时，必须明确展示不一致，不能写成一致",
                line=front_offsets.get("执行对象"),
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
                    f"首页最终观察对象 {final_target} 与推导链最终对象 {mismatched[0]} 不一致",
                )
            )
    elif len(chain_identities) > 1:
        findings.append(
            _finding(
                "sniper_target_derivation_mismatch",
                f"推导链里出现多个不一致的最终对象：{', '.join(chain_identities)}",
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


def _extract_selection_workflow_final_position_pct(lines):
    text = "\n".join(str(line or "") for line in lines or [])
    if "selection_workflow.v1" in text:
        match = re.search(
            r'"selection_workflow"\s*:\s*\{.*?"schema_version"\s*:\s*"selection_workflow\.v1".*?'
            r'"final"\s*:\s*\{.*?"position_pct"\s*:\s*(?P<pct>0|50|100)(?:\.0)?',
            text,
            re.DOTALL,
        )
        if match:
            return int(match.group("pct"))
    final_match = re.search(
        r"FINAL\[.*?仓位[：:]\s*(?P<pct>0|50|100)%",
        text,
        re.DOTALL,
    )
    if final_match:
        return int(final_match.group("pct"))
    for line in lines or []:
        cells = _split_md_row(line)
        if len(cells) < 3 or cells[0] != "最终结果":
            continue
        pct_match = re.search(r"(?<!\d)(0|50|100)%", " ".join(cells[2:]))
        if pct_match:
            return int(pct_match.group(1))
    return None


def _extract_front_position_pct(lines):
    front = _front_page_lines(lines)
    labels = ("明日新仓", "明日仓位", "仓位姿态", "进攻仓位三态", "明日最大仓位")
    for label in labels:
        value, offset = _extract_front_kv_value(front, label)
        pct_match = re.search(r"(?<!\d)(0|50|100)%", str(value or ""))
        if pct_match:
            return int(pct_match.group(1)), offset
    return None, None


def _selection_workflow_declares_empty_final(lines):
    text = "\n".join(str(line or "") for line in lines or [])
    empty_markers = (
        "FINAL[\"最终：暂无<br/>仓位：0%\"]",
        "FINAL[&quot;最终：暂无&lt;br/&gt;仓位：0%&quot;]",
        "最终：暂无<br/>仓位：0%",
        "FINAL[\"最终：暂无\\n仓位：0%\"]",
        "FINAL[&quot;最终：暂无\\n仓位：0%&quot;]",
        "最终：暂无\\n仓位：0%",
        "| 最终结果 | N9 / final | 无；0%不参与；0% |",
        "<td>最终结果</td><td>N9 / final</td><td>无；0%不参与；0%</td>",
    )
    return any(marker in text for marker in empty_markers)


def _audit_selection_workflow_consistency(lines):
    workflow_identity = _extract_selection_workflow_final_identity(lines)
    workflow_position_pct = _extract_selection_workflow_final_position_pct(lines)
    front_position_pct, front_position_offset = _extract_front_position_pct(lines)
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
    findings = []
    for value in front_values:
        identity = _target_identity(value)
        if identity and identity not in front_identities:
            front_identities.append(identity)
    if (
        workflow_position_pct is not None
        and front_position_pct is not None
        and workflow_position_pct != front_position_pct
    ):
        findings.append(
            _finding(
                "selection_workflow_position_mismatch",
                f"选股流程最终仓位为 {workflow_position_pct}%，但首页当前仓位为 {front_position_pct}%",
                line=front_position_offset,
            )
        )
    if not workflow_identity:
        if _selection_workflow_declares_empty_final(lines) and front_identities:
            findings.append(
                _finding(
                    "selection_workflow_mismatch",
                    f"选股流程最终对象为空，但首页仍写了 {front_identities[0]}",
                )
            )
        return findings
    if front_execution_object and _is_empty_target(front_execution_object):
        findings.append(
            _finding(
                "selection_workflow_mismatch",
                f"首页执行对象为空，但选股流程最终对象为 {workflow_identity}",
            )
        )
        return findings
    if not front_identities:
        return findings
    if workflow_identity in front_identities:
        return findings
    findings.append(
        _finding(
            "selection_workflow_mismatch",
            f"首页对象 {front_identities[0]} 与选股流程最终对象 {workflow_identity} 不一致",
        )
    )
    return findings


def _audit_empty_final_object_candidate_status(lines):
    if not (_front_declares_no_current_object(lines) or _selection_workflow_declares_empty_final(lines)):
        return []
    findings = []
    for index, line in enumerate(lines or [], 1):
        text = str(line or "")
        if "已归入明日执行结论" not in text and "B1/B2执行计划展示" not in text:
            continue
        findings.append(
            _finding(
                "empty_final_object_candidate_status_conflict",
                "最终对象为空，但候选仍声称已进入明日执行结论",
                line=index,
            )
        )
    return findings


def _audit_process_candidate_summary_consistency(lines):
    candidate_counts = []
    for line in lines or []:
        candidate_counts.extend(
            int(match.group("count"))
            for match in re.finditer(r"归一候选\s*(?P<count>\d+)\s*只", str(line or ""))
        )
    if not candidate_counts or max(candidate_counts) <= 0:
        return []
    no_process_candidate_pattern = re.compile(
        r"(?:也)?没有(?:任何|可用)?过程候选|无(?:可用)?过程候选|"
        r"过程候选(?:数|数量)?\s*(?:为|[:：])\s*0(?:只|个)?"
    )
    findings = []
    for index, line in enumerate(lines or [], 1):
        if not no_process_candidate_pattern.search(str(line or "")):
            continue
        findings.append(
            _finding(
                "process_candidate_summary_conflict",
                f"选股流程已有 {max(candidate_counts)} 个过程候选，但摘要写成没有过程候选",
                line=index,
            )
        )
    return findings


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
                f"首页观察对象 {final_target} 与附录观察对象 {anchor_identity} 不一致",
            )
        )
    first_watch_identity = _extract_first_watch_order_identity(appendix)
    if first_watch_identity and first_watch_identity != final_identity:
        findings.append(
            _finding(
                "observation_anchor_mismatch",
                f"首页观察对象 {final_target} 与附录首个观察顺序对象 {first_watch_identity} 不一致",
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
    identity = _target_identity(stripped)
    is_process_line = bool(identity) and any(marker in stripped for marker in process_markers)
    if is_process_line:
        if re.search(
            r"(?:观察价|预估|最晚|失效价|确认价|买入价|支撑/失效)[^|\n]{0,24}\d+(?:\.\d+)?",
            stripped,
        ):
            return "过程候选仍带未来观察价（未来价位）"
        if "可作为主对象" in stripped:
            return "过程候选仍带可作为主对象结论"
        if re.search(r"(?:身份|角色|对象口径)\s*[:：]\s*板块锚", stripped) and not any(
            marker in stripped for marker in ("未证明", "不是", "不能", "缺少", "未识别", "不属于", "不具备")
        ):
            return "过程候选仍带板块锚身份"
    if "明天重点候选组" in stripped:
        return "明天重点候选组"
    tomorrow_watch_match = re.search(
        r"(?P<label>(?:跨线)?明天先盯哪只)(?:\*\*)?\s*[:：]\s*(?P<target>[^|\n]+)",
        stripped,
    )
    if tomorrow_watch_match:
        target_text = str(tomorrow_watch_match.group("target") or "").strip()
        if target_text and not _is_empty_target(target_text) and _target_identity(target_text):
            return tomorrow_watch_match.group("label")
    if re.search(r"09:50-10:10观察价(?:待盘中确认|\d+(?:\.\d+)?)", stripped) and _target_identity(stripped):
        return "未来观察价"
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
        if _target_identity(" ".join(cells)) and any(cell in {"可做", "50%条件执行", "100%核心进攻"} for cell in cells):
            return "明日资格=可做"
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


def _front_positive_execution_identity(lines):
    front = _front_page_lines(lines)
    if _final_summary_is_zero_position(front):
        return ""
    for value in (
        _extract_opening_verdict_final_object(front),
        _extract_front_execution_object(lines),
        _extract_execution_unique_target(front),
        _extract_final_unique_target(front),
        _extract_closing_action_target(front),
    ):
        identity = _target_identity(value)
        if identity and not _is_empty_target(value):
            return identity
    return ""


def _audit_positive_final_action_appendix_conflicts(lines):
    identity = _front_positive_execution_identity(lines)
    if not identity:
        return []
    appendix = _appendix_lines(lines)
    if not appendix:
        return []
    appendix_start_line = len(lines) - len(appendix)
    conflict_markers = (
        "还没有缩到一只可买股",
        "还没有缩到一只合格参与对象",
        "市场允许出手，但还没有",
        "市场已允许出手，但还没有",
        "当前还在等待层",
        "明天仓位放多少**: 0%",
        "0%（市场允许出手",
        "明天先盯哪只",
        "唯一能买",
        "可买股",
        "可买对象",
        "买点出现",
        "预计算买点",
        "筛到可买股",
        "明日买入决定：不买新仓；观察对象只复盘，不参与",
        "只做等待，不做新增参与",
        "保持空仓：当前不新增参与",
        "禁止买入任何方向",
        "明日不新增参与",
        "继续0%不参与",
        "进攻仓位**: 0%不参与",
        "盘前0%就是不买新仓",
        "当前是0%不参与，本时段只观察主线核心是否在固定交易窗口内满足条件",
        "未确认保持0%",
    )
    process_markers = ("过程候选", "过程样本", "过程证据", "回看样本", "不覆盖唯一明日动作")
    findings = []
    in_ignored_candidate_block = False
    in_positive_execution_table = False
    for index, line in enumerate(appendix, 1):
        text = str(line or "")
        stripped = text.strip()
        if stripped.startswith("#") and "明日条件执行对象" in stripped:
            in_positive_execution_table = True
        elif in_positive_execution_table and stripped.startswith("#"):
            in_positive_execution_table = False
        if stripped.startswith("**暂不关注**:"):
            in_ignored_candidate_block = True
        elif in_ignored_candidate_block and (not stripped or stripped.startswith("**") or stripped.startswith("#")):
            in_ignored_candidate_block = False
        if in_ignored_candidate_block and identity and identity in _target_identity(text):
            findings.append(
                _finding(
                    "positive_final_action_appendix_conflict",
                    f"前台已有正向唯一动作 {identity}，附录仍把同一对象放入暂不关注或条件链不足分组",
                    line=appendix_start_line + index,
                )
            )
            continue
        if any(marker in text for marker in conflict_markers):
            findings.append(
                _finding(
                    "positive_final_action_appendix_conflict",
                    f"前台已有正向唯一动作 {identity}，附录仍保留无对象或0%旧口径",
                    line=appendix_start_line + index,
                )
            )
            continue
        if identity and identity in _target_identity(text) and any(
            marker in text for marker in ("候选观察", "需看明日竞价强弱", "不作为新增参与依据", "最终0%时只作观察样本")
        ):
            findings.append(
                _finding(
                    "positive_final_action_appendix_conflict",
                    f"前台已有正向唯一动作 {identity}，附录仍把同一对象写成观察或0%旧口径",
                    line=appendix_start_line + index,
                )
            )
            continue
        if stripped.startswith(
            (
                "**观察优先对象**",
                _m("**观察优先", "锚点**"),
                "- **盘前不抢跑**:",
                "- **跨线继续看谁**:",
                "- **现在重点看什么**:",
            )
        ):
            line_identity = _target_identity(stripped)
            if line_identity and line_identity != identity and not any(marker in text for marker in process_markers):
                findings.append(
                    _finding(
                        "positive_final_action_appendix_conflict",
                        f"前台已有正向唯一动作 {identity}，附录仍把 {line_identity} 写成当前观察优先对象",
                        line=appendix_start_line + index,
                    )
                )
                continue
        cells = _split_md_row(text)
        if not cells:
            continue
        if "明天具体怎么做" in cells and "股票" in cells:
            continue
        if len(cells) >= 2 and cells[0] == "角色" and "标的" in cells:
            continue
        if len(cells) >= 2 and cells[0] in {"明日主买对象", "明日补位对象"}:
            row_identity = _target_identity(" ".join(cells[1:]))
            if row_identity and row_identity != identity and not any(marker in text for marker in process_markers):
                findings.append(
                    _finding(
                        "positive_final_action_appendix_conflict",
                        f"前台已有正向唯一动作 {identity}，附录仍把 {row_identity} 写成明日主买或补位对象",
                        line=appendix_start_line + index,
                    )
                )
                continue
        if in_positive_execution_table and len(cells) >= 2 and cells[0] in {"暂无", "无"}:
            findings.append(
                _finding(
                    "positive_final_action_appendix_conflict",
                    f"前台已有正向唯一动作 {identity}，附录明日条件执行对象表仍为空",
                    line=appendix_start_line + index,
                )
            )
            continue
        if len(cells) >= 3 and any("明天先盯哪只" in cell or "确认后执行预案" in cell for cell in cells):
            row_identity = _target_identity(" ".join(cells))
            if row_identity and row_identity != identity and not any(marker in text for marker in process_markers):
                findings.append(
                    _finding(
                        "positive_final_action_appendix_conflict",
                        f"前台已有正向唯一动作 {identity}，附录最终动作表仍指向 {row_identity}",
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
                f"执行对象 {execution_target} 与最终摘要对象 {final_target} 不一致",
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
                f"执行对象 {execution_target} 与最终摘要对象 {final_target} 不一致",
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
            f"具体唯一对象 {target} 缺少首页决策证据：{', '.join(missing)}",
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
                "唯一对象为空，但首页仍把具体股票写成可参与或可执行",
                line=offset + 1,
            )
        )
    return findings


def audit_report_markdown(
    markdown,
    companion_html=None,
    source_path=None,
    *,
    position_companion_html=None,
    expected_position_summary=None,
    expected_turnover_rows=None,
    prefer_postgres_history=False,
):
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
    findings.extend(_audit_front_execution_object_limit_down_without_reversal_plan(lines))
    findings.extend(_audit_appendix_duplicate_front_page_sections(lines))
    findings.extend(_audit_duplicate_no_trade(lines))
    findings.extend(_audit_front_page_duplicate_long_cells(lines))
    findings.extend(_audit_degraded_fake_zero(lines))
    findings.extend(_audit_turnover_core_quote_completeness(lines))
    findings.extend(_audit_turnover_core_source_consistency(lines, expected_turnover_rows))
    findings.extend(_audit_market_breadth_incomplete(lines))
    findings.extend(_audit_position_context_contradictions(lines))
    timeline_companion_html = position_companion_html if position_companion_html is not None else companion_html
    findings.extend(
        _audit_position_timeline_parity(
            lines,
            timeline_companion_html,
            require_html_timeline=position_companion_html is not None,
        )
    )
    findings.extend(_audit_position_timeline_final_conflict(lines))
    findings.extend(_audit_position_day_order_execution_target(lines, timeline_companion_html))
    findings.extend(
        _audit_position_day_order_current_position(
            lines,
            companion_html=timeline_companion_html,
            expected_position_summary=expected_position_summary,
        )
    )
    findings.extend(
        _audit_position_day_order_history_paths(
            lines,
            source_path=source_path,
            prefer_postgres_history=prefer_postgres_history,
        )
    )
    findings.extend(_audit_account_advice_position_contract(lines))
    findings.extend(_audit_position_action_semantics(lines))
    findings.extend(
        _audit_position_action_html_semantics(
            lines,
            timeline_companion_html,
            require_html_account_action=position_companion_html is not None,
        )
    )
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
    findings.extend(_audit_daily_judgment_settled_fact_visibility(lines))
    findings.extend(_audit_derivation_audit_rejection_consistency(lines))
    findings.extend(_audit_process_candidate_loss_reasons(lines))
    findings.extend(_audit_bayesian_diagnosis_contract(lines))
    findings.extend(_audit_sniper_target_derivation_consistency(lines))
    findings.extend(_audit_selection_workflow_consistency(lines))
    findings.extend(_audit_empty_final_object_candidate_status(lines))
    findings.extend(_audit_process_candidate_summary_consistency(lines))
    findings.extend(_audit_positive_final_action_appendix_conflicts(lines))
    findings.extend(_audit_observation_anchor_consistency(lines))
    findings.extend(_audit_empty_final_object_appendix_current_object(lines))
    findings.extend(_audit_zero_position_decision_attribution(lines))
    findings.extend(_audit_zero_position_tomorrow_action_consistency(lines))
    findings.extend(_audit_zero_position_participation_language(lines))
    findings.extend(_audit_premarket_fixed_decision_language(lines))
    findings.extend(_audit_position_tier_visible_language(lines))
    findings.extend(_audit_one_shot_buy_wording(lines))
    findings.extend(_audit_legacy_timeline_qualification_wording(lines))
    findings.extend(_audit_legacy_execution_object_surface_wording(lines))
    findings.extend(_audit_market_snapshot_risk_consistency(lines))
    findings.extend(_audit_sector_fund_flow_visible_zero_tables(lines))
    findings.extend(_audit_positive_premarket_fixed_decision_language(lines))
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
    result = audit_report_markdown(path.read_text(encoding="utf-8"), companion_html=companion_html, source_path=path)
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
