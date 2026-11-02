"""A dated, independent reading of the day written by a language model from a closed fact pack.

The model sees only facts dated on or before the target day. Every number it writes must be
traceable to the fact pack; banned or position-sizing words reject a sample. Several samples
are drawn: the majority stance leads, and minority views are kept rather than averaged away.
The result is frozen in the snapshot, so replays never call the model again.
"""
from collections import Counter
from datetime import date, datetime, timedelta
import hashlib
import json
import re
from zoneinfo import ZoneInfo

from report.sector_reading_history import evidence_hash

SCHEMA = 'daily_interpretation.v1'
STANCES = ('防守', '均衡', '进攻')
BANNED = ('门禁', 'gate', '状态机', '仓', 'B1', 'B2', '梭哈', '加杠杆')
SAMPLES = 3
WEEKDAYS = ('周一', '周二', '周三', '周四', '周五', '周六', '周日')

SYSTEM_PROMPT = """你是A股短线交易者的研究助手，每天收盘后根据给定事实写一段当日解读。

用户的定义与偏好（必须遵守）：
- 阿尔法：个股自己的独立行情，与大盘涨跌关系不大。贝塔：大盘涨跌带动个股共振的行情。板块成员一起涨不等于贝塔，跑赢板块不等于阿尔法。
- 用户认可“利好就是利空”。执行计划的卖法（2026-10-31 用户采纳）：持有的股票收盘比买价高10%，下一个交易日开盘卖，卖出的钱留到下一个换手日、这一期不再买回；这一条代替原来的高开兑现；不设止损。
- 不上杠杆。没有最好的投资流派：价值、短线、超短线都不天然更好，只看能否赚钱、收益是否明确、做法能否重复。
- 比较做法时，除中证全指外也看创业板指、科创50和等权平均；只和中证全指比会高估规则。用户以创业板指为锚：跑不赢它、或回撤比它还深的做法不值得执行。
- 执行计划是小盘轮换：每20个交易日在收盘后定一次名单，下一个交易日开盘换股，买业绩为正里成交额最小的5只，期间名单不变。收益主要来自“冷门且业绩增长”的整个股票池，名单只是抽样；评价名单时和同期股票池、中证2000一起比，名单比股票池差多半是运气，股票池跑输中证2000才说明这个条件可能失效。“下一个交易日怎么做”要围绕执行计划写（要不要换股、持有第几天、名单与备选）；大盘阶段、阿尔法和贝塔只作背景，不另给买入建议。“名单”只指执行计划的5只；说到检查全过的阿尔法时写“阿尔法观察”，不要简称“名单”。
- 下一个交易日的日期和星期以事实包为准：只有它正好是明天时才能说“明天”，遇到周末或假期写“下一个交易日”或“下周一”这类说法。说持有第几天时，说下一个交易日的要带这些词，其余一律指今天，两者的天数不要混用。
- 用户的原则：小亏、小赚、绝不大亏、偶尔大赚；整个账户净值跌破0.7就全部停下。用户的账户能买主板和创业板，买不了科创板，执行计划只在主板和创业板里选。
- 不知道用户的账户与持仓，不给买卖数量或资金比例，不编造未提供的事实。不要使用任何带“仓”字的说法（如轻仓、小仓、减仓、建仓），改用“少做”“不买”“卖出”“观察”。

写作要求：
- 只用事实包里的数字，原样引用（可四舍五入到事实包已有的精度），不要自己计算新数字，不写事实包里没有的股票或板块。
- 写今天特有的东西：至少点名两条“今日新现象”里的具体内容，说明它们对“下一个交易日怎么做”意味着什么；不要写放之四海皆准的套话。
- 区分事实与判断：判断用“我倾向/我认为”，并说清依据与代价。
- 立场三选一：防守、均衡、进攻。可以与“规则信号”不同，但不同时必须说明理由。
- 给一条反方意见：如果你的判断错了，最可能错在哪里。
- “今日”开头的数字只描述当天，“近20日”开头的数字描述20个交易日窗口，两者不要混用或互相比较。
- 用交易语言，不用软件流程词；禁止出现：门禁、gate、状态机、B1、B2。

只输出一个 JSON 对象，不要输出其他文字：
{"headline": "不超过36字的当日结论", "stance": "防守|均衡|进攻", "stance_reason": "不超过60字", "summary": ["3到5句解读，每句不超过80字"], "action": "下一个交易日具体怎么做，不超过100字", "dissent": "反方意见，不超过80字", "cited": ["引用的新现象id"]}"""


def fact_pack(target_date, projection, board, observations, backtest=None, plan=None):
    regime = projection['regime']
    pack = {
        '日期': target_date,
        '大盘': {'今日中证全指涨跌%': regime['market_pct'], '今日个股中位数涨跌%': regime['median_pct'],
                 '今日上涨家数': regime['up_count'], '今日下跌家数': regime['down_count'],
                 '今日与大盘同向比例%': regime['same_share'], '中证全指近20日涨跌%': board['market']['return20_pct'],
                 '收盘较20日均价%': board['market']['gap_to_ma20_pct']},
        '贝塔与阿尔法': {'近20日共振度': regime['sync'], '近20日共振度在近两个月的百分位': regime['sync_rank'],
                       '大盘带动': regime['strength'], '近20日独立上涨只数': regime['alpha_up'], '近20日抗跌只数': regime['resilient'],
                       '近20日独立收益显著为正的只数': regime['outperform'],
                       '近20日随机情况下预期的显著只数': regime['expected']},
        '规则信号': {'总体': board['stance_text'], '贝塔': board['action_keys']['beta'], '阿尔法': board['action_keys']['alpha']},
        '今日新现象': [{'id': o['id'], '标题': o['title'], '内容': o['text']} for o in observations['items']],
        '检查全过的阿尔法': [{'名称': c['name'], '代码': c['code'], '行业': c['industry'], '20日涨跌%': c['total_pct'],
                         '独立收益个百分点': c['own_pp'], '贝塔': c['beta'], '大盘跌日平均%': c['down_mean_pct'],
                         '失效价': c['stop'], '失效价距现价%': c['stop_distance_pct'], '今日涨跌%': c['today_pct']}
                        for c in board['candidates'] if c['status'] == 'buy'],
        '等回调的阿尔法': [c['name'] for c in board['candidates'] if c['status'] == 'wait'][:8],
        '高贝塔篮子': [{'名称': c['name'], '贝塔': c['beta'], '20日涨跌%': c['total_pct']} for c in board['beta_basket'][:5]],
        '近两个月同规则前推': {
            '检查全过阿尔法5日后相对中证全指个百分点': board['walk_forward']['summary']['alpha']['mean_excess'],
            '阿尔法跑赢比例': board['walk_forward']['summary']['alpha']['hit_rate'],
            '高贝塔5日后相对中证全指个百分点': board['walk_forward']['summary']['beta']['mean_excess'],
            '决策日数': board['walk_forward']['summary']['decision_dates']},
        '情景_大盘再跌2%': {'阿尔法组%': (board['pk']['alpha'] or {}).get('down_scenario_pct'),
                        '高贝塔组%': (board['pk']['beta'] or {}).get('down_scenario_pct')},
        '改判断信号': [{'信号': t['text'], '现在': t['now'], '已出现': t['met']} for t in board['triggers']],
    }
    if backtest:
        pack['长期回测'] = backtest
    if plan:
        holding = plan.get('holding') or {}
        pack['执行计划'] = {'本期定名单日': plan['decision_date'], '今天是持有第几个交易日': plan['sessions_since'],
                        '下一个交易日': _day_text(plan.get('next_session')),
                        '下一个交易日是持有第几个交易日': plan['sessions_since'] + 1,
                        '下一个交易日要不要换股': '要' if plan['sessions_since'] == 0 else '不要',
                        '下次定新名单的日子': _day_text(plan.get('next_decision')),
                        '今天收盘后距下次定新名单还有几个交易日': plan['sessions_to_next'], '名单': [p['name'] for p in plan['picks']],
                        '备选': [p['name'] for p in plan['backups']], '本期实际买入': holding.get('names'),
                        '本期以来合计%': holding.get('basket_pct'), '同期股票池%': holding.get('pool_pct'),
                        '同期中证2000%': holding.get('csi2000_pct'), '同期创业板指%': holding.get('chinext_pct'),
                        '同期中证全指%': holding.get('csi_all_pct'), '不止盈对照合计%': holding.get('basket_hold_pct')}
        orders = (plan.get('account') or {}).get('orders') or []
        if plan.get('take_profit'):
            pack['执行计划'].update({'卖法': '收盘比买价高10%，下一个交易日开盘卖，卖出的钱留到下一个换手日',
                                  '今天收盘到止盈线、下一个交易日开盘卖': [o['name'] for o in orders if o.get('status') == 'due'],
                                  '本期已止盈卖出': [o['name'] for o in orders if o.get('status') == 'sold']})
    return _rounded(pack)


def _day_text(day):
    return f"{day}（{WEEKDAYS[date.fromisoformat(day).weekday()]}）" if day else '未知'


def _rounded(value):
    if isinstance(value, float):
        return round(value, 2)
    if isinstance(value, dict):
        return {k: _rounded(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_rounded(v) for v in value]
    return value


def _numbers(text):
    return [m.group(0) for m in re.finditer(r'(?<![\d.])-?\d+(?:\.\d+)?', text)]


def _grounded_numbers(pack):
    """Every number form a writer could take from the pack: as given, rounded, absolute, as percent."""
    allowed = set()

    def add(number):
        for digits in (0, 1, 2):
            for value in (number, abs(number), number * 100, abs(number) * 100):
                allowed.add(f'{round(value, digits):.{digits}f}')
    text = json.dumps(pack, ensure_ascii=False)
    for token in _numbers(text):
        add(float(token))
    return allowed


def validate_sample(sample, pack):
    """Return a list of reasons the sample cannot be used; empty means usable."""
    problems = []
    if not isinstance(sample, dict):
        return ['不是 JSON 对象']
    fields = ('headline', 'stance', 'stance_reason', 'summary', 'action', 'dissent')
    for field in fields:
        if field not in sample:
            problems.append(f'缺少{field}')
    if problems:
        return problems
    if sample['stance'] not in STANCES:
        problems.append('立场不在三选一之内')
    summary = sample['summary']
    if not isinstance(summary, list) or not 2 <= len(summary) <= 6 or not all(isinstance(s, str) for s in summary):
        problems.append('解读句数不符')
        summary = []
    texts = [sample['headline'], sample['stance_reason'], sample['action'], sample['dissent'], *summary]
    if not all(isinstance(t, str) and t.strip() for t in texts):
        return problems + ['存在空字段']
    if len(sample['headline']) > 48:
        problems.append('标题过长')
    joined = '\n'.join(texts)
    for word in BANNED:
        if word.lower() in joined.lower():
            problems.append(f'含禁用词：{word}')
    plan = pack.get('执行计划')
    if plan:
        problems += _holding_day_problems(texts, pack['日期'], plan)
    allowed = _grounded_numbers(pack)
    for token in _numbers(joined):
        number = float(token)
        if abs(number) <= 10 and float(number).is_integer():
            continue
        forms = {f'{round(number, d):.{d}f}' for d in (0, 1, 2)} | {token.lstrip('-')}
        if not forms & allowed:
            problems.append(f'数字无出处：{token}')
    return problems


def _holding_day_problems(texts, target_date, plan):
    """A holding-day count belongs to the next session only when its clause names it (下一个交易日, its weekday or
    date, 明天, 次日); otherwise it must be today's. 明天 is refused when the next session is not the next day."""
    today, upcoming = plan['今天是持有第几个交易日'], plan['下一个交易日是持有第几个交易日']
    nxt = (plan.get('下一个交易日') or '未知')[:10]
    markers = ['明天', '次日', '下一个交易日', '下个交易日', '下一交易日', '下周']
    problems = []
    if nxt != '未知':
        day = date.fromisoformat(nxt)
        markers += [WEEKDAYS[day.weekday()], f'{day.month}月{day.day}日', nxt[5:]]
        if day != date.fromisoformat(target_date) + timedelta(days=1) and any('明天' in t for t in texts):
            problems.append(f'下一个交易日是{nxt}，不是明天')
    for text in texts:
        for clause in re.split(r'[。；;，,、！？!?\n]', text):
            for match in re.finditer(r'持有(?:的)?第(\d+)', clause):
                said = clause[:match.start()]
                expected = upcoming if any(m in said for m in markers) else today
                if int(match.group(1)) != expected:
                    problems.append(f'持有天数与今天、下一个交易日不符：{clause.strip()}')
    return problems


def _parse(content):
    match = re.search(r'\{.*\}', content or '', re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def generate_interpretation(target_date, pack, *, service=None, samples=SAMPLES, temperature=0.8):
    if service is None:
        from llm_service import get_llm_service
        service = get_llm_service()
    prompt = '以下是今日事实包（JSON）。请按要求输出 JSON：\n' + json.dumps(pack, ensure_ascii=False)
    usable, failures = [], []
    for k in range(samples):
        for attempt in range(2):
            result = service.chat_with_metadata(prompt, system_prompt=SYSTEM_PROMPT, temperature=temperature,
                                                max_tokens=4000, max_retries=1)
            sample = _parse(result.get('content'))
            if sample is not None:
                break
        problems = validate_sample(sample, pack)
        if problems:
            failures.append({'sample': k, 'problems': problems[:6]})
            continue
        usable.append({'sample': k, **{key: sample[key] for key in ('headline', 'stance', 'stance_reason', 'summary',
                                                                   'action', 'dissent')},
                       'cited': [c for c in sample.get('cited') or [] if isinstance(c, str)][:6]})
    if not usable:
        return None
    votes = Counter(item['stance'] for item in usable)
    leading = max(votes.items(), key=lambda kv: (kv[1], -STANCES.index(kv[0])))[0]
    chosen = next(i for i, item in enumerate(usable) if item['stance'] == leading)
    value = {
        'schema': SCHEMA, 'target_date': target_date,
        'generated_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
        'model': getattr(service, 'model', 'unknown'), 'provider': getattr(service, 'provider_name', 'unknown'),
        'prompt_sha256': hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),
        'facts_hash': evidence_hash(pack), 'requested_samples': samples,
        'samples': usable, 'failures': failures, 'votes': dict(votes), 'chosen': chosen,
        'rule_stance': pack['规则信号']['总体'],
    }
    value['artifact_hash'] = evidence_hash(value)
    return value


def validate_interpretation(value, target_date):
    if (not isinstance(value, dict) or value.get('schema') != SCHEMA or value.get('target_date') != target_date
            or value.get('artifact_hash') != evidence_hash({k: v for k, v in value.items() if k != 'artifact_hash'})
            or not value.get('samples') or not 0 <= value.get('chosen', -1) < len(value['samples'])):
        raise ValueError('当日解读日期或指纹不符')
    if value['generated_at'][:10] < target_date:
        raise ValueError('当日解读生成时间早于目标日')
    return value
