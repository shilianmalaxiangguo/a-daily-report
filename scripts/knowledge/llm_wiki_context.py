"""Compact Chinese LLM Wiki context for the daily-report pipeline."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Mapping
from zoneinfo import ZoneInfo

from knowledge.llm_wiki_manifest import (
    VALID_MANIFEST_AVAILABILITIES,
    build_knowledge_manifest,
    is_sha256,
    stable_json_hash,
    validate_knowledge_manifest,
    validate_knowledge_manifest_sources,
)
from knowledge.llm_wiki_router import (
    DECISION_FIELDS_EXCLUDED_FROM_KNOWLEDGE,
    EXPLICIT_FACT_PATHS,
    KNOWLEDGE_INDEX,
    is_iso_calendar_date,
)


WIKI_VERSION = "2026-08-30"
WIKI_SOURCE = "llm_wiki"
WIKI_LANGUAGE = "zh-CN"
ROOT = Path(__file__).resolve().parents[2]
_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
_AVAILABILITY_CONFIDENCE = {
    "ready": 1.0,
    "partial": 0.8,
    "missing_sources": 0.4,
    "source_changed": 0.4,
    "invalid": 0.0,
    "historical_trace_missing": 0.0,
    "decision_mismatch": 0.0,
}
_LEGACY_DECISION_FIELDS_EXCLUDED_FROM_KNOWLEDGE = tuple(
    field
    for field in DECISION_FIELDS_EXCLUDED_FROM_KNOWLEDGE
    if field
    not in {
        "execution_nature",
        "planned_participation",
        "account_action",
        "tomorrow_account_action",
    }
)


def llm_wiki_confidence_for_availability(availability: object) -> float:
    return _AVAILABILITY_CONFIDENCE.get(str(availability or "").strip(), 0.0)

SOURCE_PATHS = [
    "wiki/README.md",
    "wiki/交易思想/价格行为与能量框架.md",
    "wiki/交易思想/布鲁克斯价格行为趋势.md",
    "wiki/交易思想/反伪精确第一性原理.md",
    "wiki/交易思想/启动板与趋势持股短板.md",
    "wiki/交易思想/极度看好参与时机.md",
    "wiki/交易思想/交易错题本.md",
    "wiki/交易思想/做T与风险控制.md",
    "wiki/交易思想/新股周期与市场情绪.md",
    "wiki/交易思想/扣分系统与动作分层.md",
    "wiki/交易思想/实际账户情况.md",
    "wiki/交易思想/判断样本与市场演变.md",
    "wiki/交易思想/AI摩擦与知识复利.md",
    "wiki/板块补充/供应链瓶颈研究法.md",
    "wiki/板块补充/板块中枢与主线延续.md",
    "wiki/交易思想/创新高扩散、核心独强与补跌.md",
    "wiki/交易思想/历史先验、实时结构与可用窗口.md",
    "wiki/交易思想/系统性下跌后的剩余风险.md",
    "wiki/交易思想/企业估值与价格执行的双周期框架.md",
    "wiki/交易思想/缠论体系.md",
    "wiki/交易思想/缠论-日报使用边界.md",
    "wiki/交易思想/日报术语契约.md",
    "wiki/运行契约/日报数据源契约.md",
    "wiki/运行契约/LLM Wiki维护与路由契约.md",
    "wiki/交易思想/缠论-级别联立.md",
    "wiki/资料库/缠论原文索引.md",
    "wiki/资料库/时空乐道0704早信与周期.md",
]

DATED_SOURCE_PATHS = [
    {
        "knowledge_id": "market.new-high-core-trend-anchor",
        "path": "wiki/交易思想/2026-08-18核心新高趋势锚补充.md",
    },
    {
        "knowledge_id": "market.rotation-focus-carrier-separation",
        "path": "wiki/板块补充/2026-08-18轮动聚焦与资金载体分周期补充.md",
    },
    {
        "knowledge_id": "market.auction-delayed-sell-pressure-bayesian",
        "path": "wiki/交易思想/2026-08-28竞价未充分定价与延迟卖盘.md",
    },
    {
        "knowledge_id": "market.polarization-negative-alliance-energy",
        "path": "wiki/交易思想/2026-08-29共同排斥、双峰聚集与市场能量.md",
    },
    {
        "knowledge_id": "market.polarization-negative-alliance-energy",
        "path": "wiki/资料库/2026-08-28V2EX同质性网络、虚假共识与双峰形成讨论整理.md",
    },
    {
        "knowledge_id": "market.august-hot-stock-double-cluster-migration",
        "path": "wiki/交易思想/2026-08-30八月热门股双群聚与动态极点迁移.md",
    },
]

FIELD_MAPPINGS = [
    "日线结构中枢定环境 -> 固定交易窗口条件 -> 失效价和单笔-5%底线",
    "普通结构观察 -> 09:50-10:10窗口；强核心快路径 -> 09:30-09:35竞价表态、开盘前几分钟或回封",
    "参与时机 -> open_core开盘核心 / ten_confirm 09:50-10:10窗口 / tail_exception尾盘14:30-14:55例外 / no_trade不交易",
    "买卖窗口期 -> 只在09:30-09:35、09:50-10:10、14:30-14:55三段处理买卖；窗口外不新增买卖动作，只等待下一窗口或处理既定风险",
    "Ta-Te账户日序表 -> Ta最远复盘日，Tb/Tc是前两段路径，Td是报告日，Te是明日执行日；Te只承接昨晚决定的参与、取消或旧仓降风险",
    "上一日明日标的继承 -> 模拟账户把前日报明日标在次交易日默认视为必买完成，直接成为1x/50%旧仓与B1；无新明日标不自动清仓，明确当前空仓、已执行明日空仓或退出事实才结束；external_trade_pending仍按实际0x待核实",
    "1x/2x仓位档 -> 账户只有0、1x/50%半仓和2x/100%满仓三档；前日报旧仓1x与新仓1x合计2x/100%，不是200%；同股B2确认后也只从1x升到2x",
    "仓位暴露字段 -> planned_new_entry_pct/x是计划总档；new_entry_pct/x是扣除旧仓或账户空间后的当前新增档；两者不能互换",
    "明日新仓0%或明日标的为空 -> 只表示不新增参与；已确认旧仓按独立旧仓计划处理，持仓未知保持待确认，不得写成明日空仓",
    "显式明日空仓 -> 次日不买新股；集合竞价卖清全部可卖旧仓；成交后账户仓位0；不做T；未成交继续尽早卖，未清完不能称空仓",
    "明日空仓优先级 -> 只有显式明日空仓才覆盖已经失败、待10:10复核和正常T+2的常规旧仓处理时点；明日新仓0%、明日标的为空、当前空仓和持仓未知都不触发覆盖",
    "统一来源 -> 日报写入decision-ledger planned_participation，报告和复盘只消费同一份结构化计划，不各自重算",
    "最终对象统一口径 -> 板块锚反推先选强对象，小账户资金取舍再定资金优先，最后只生成明日唯一动作或观察对象",
    "最终对象角色拆分 -> new_entry_target新开仓对象 / existing_position_target旧仓处理对象 / tradable_proxy_target小资金可交易替代表达 / watch_target观察对象 / process_target过程对象 / display_target最终动作显示对象",
    "小账户资金取舍结果 -> capital_priority=new_entry_after_old_exit时旧仓只是腾资金动作，新核心仍是最终对象",
    "极度看好复盘 -> 日报生成时用行情表回写participation_review，封死买不到不算收益命中",
    "明日主买对象 -> 非0%且参与资格成立时给1只主买和1只补位；最终0%时统一降为候选观察",
    "前台收口 -> 0%不参与、唯一对象暂无或只给观察资格时，所有明日动作面板只写观察，不写主买补位或新增参与",
    "反预测崇拜与应对剧本 -> 日报不是预测节拍，而是判断有没有可参与动作；没有明确买入资格时0%不参与也是有效结论",
    "第一动作分层 -> 第一根阳线、指数翻红或板块回暖只给观察信号或B1参与权，不直接给B2确认权",
    "量化行为博弈 -> 日报同时识别市场动作和散户一致行为陷阱，避免把踏空焦虑、回本卖出、小赚止盈或阳线追后排当成交易理由",
    "创新高趋势生成率 -> 先看当日新高数、跨日变化、窗口峰值保留率和板块成群度；首次个位数只给结构预警，来源或板块归属不足时只作结构观察，不直接改变候选、仓位、B1/B2或退出动作",
    "节奏复位不新增 -> 0%不是思考终点；旧目标尾端或步伐踏错时先停下来，再反推边际主线和次日复核路径",
    "延后确认不新增 -> T0看到可能新主线但板块扩散、A股映射、承接窗口或亏损边界不完整，只进入T+1复核",
    "错失待批改 -> 次日事实只用于批改是否过度防守或漏判，不回写T0结论，也不把过程候选写成明日执行对象",
    "公共合理不等于超短边际 -> 合理不新增可以保命，但超短还要解释有没有边际主线、旧目标尾端和确认延后",
    "旧信号源批改 -> 周一不新增且旧目标来自周五信号时，必须批改周五选股、买点、持仓预期和退出纪律；周二走强只算重新比较，不替周五或周一正名",
    "狙击手推导顺序 -> 先判退潮，再取候选，再做最终风险复核，再判龙头速度档和买卖线，最后比较共同选择一致性",
    "龙头速度档 -> 极致加速看MA3/MA5，高弹性强趋势看MA5/MA10，大容量趋势看MA10/MA20",
    "共同选择一致性 -> 昨日持筹者不急卖、明日新买盘愿意接、主线资金仍有理由选择",
    "心理价位与量化锚点 -> 对子数、整数位、前高前低、VWAP、MA和成交密集区只作价格锚点，不作独立买入理由",
    "隐藏买卖盘 -> 顶部锚点冲不过按隐藏卖盘和止盈观察，底部锚点必须站回VWAP并在09:50-10:10窗口承接稳定才允许试错",
    "量化共同选择 -> 昨日持筹者、明日新买盘、主线资金、量化动量四方一致后才提高参与质量",
    "高潮反包 -> 高潮后反包优先按先手兑现点，放量吃掉压力并回踩不破才恢复候选",
    "太极实业跌停N字样本 -> 入选不是因为跌停本身，而是上一日报明日标的继承、半导体/AI硬件关注、容量成交热度、关键价带和结构性外部事件共同触发次日验证",
    "最终风险复核 -> 公告风险、连续长上影未修复、跌破对应卖点线收不回，取消主买和补位资格",
    "趋势审美复核 -> 明日极度看好先看近120日日K，上升趋势/平台震荡/缩量回踩有承接才保留；A杀/放量下杀/反抽不过关键线/高低点下移只观察",
    "选股形态审美 -> 先看120日日K的呼吸感、蛇形走位、重心上移、平台消化和缩量回踩；A杀、破位弱反抽、放量下杀不参与",
    "图形美学 -> 假底先按反抽看；真正的进攻雏形通常是小K线、缩量横盘、重心上移、靠近前高，最终等阳包阴或突破阳线确认",
    "形态待修复池 -> 历史好形态或趋势比价链样本当前承接转弱但未A杀时保留跟踪；重新站回短中线承接后再评估，继续走坏取关淘汰",
    "龙回头观察池 -> 历史辨识度仍在但A杀或弱反抽未修复时单独观察；不进正式名单，重新站回短中线承接后再评估，继续走坏取关淘汰",
    "日报固定附录 -> 必须渲染附录A：明日极度看好列表、附录A：龙回头观察池，让个股名单可快速定位",
    "选股形态流程 -> 数据源到120日日K复核、历史三表复盘、明日极度看好比较；最终0%时上证缠论、明日执行计划、明日抉择统一只观察",
    "历史观察表头 -> 重点观察25日、明日极度看好近25日、历史回测表统一使用观察位窗口/观察位质量",
    "角度与幅度 -> 上涨斜率、回撤比例、突破后承接、加速后衰竭",
    "布鲁克斯价格趋势优先 -> 所有走势最终反映到价格趋势；先看价格趋势、常用K线和收盘位置，指标组合只作辅助证据",
    "布鲁克斯A股量价本地化 -> 价格是最终裁判，成交量是资金表态；量先用于识别谁在行动，参与资格必须由价格后续确认",
    "叙事后置 -> 资金、消息、基本面和量化解释都必须反馈到图上；先看趋势、承接、跟随、失败和失效线，原因只解释背景不替代参与资格",
    "反伪精确第一性原理 -> 事实数值保留，主观判断不写成精确分；明日对象按市场板块、角色、反证、价格行为、账户条件逐层淘汰",
    "板块资金扩散找资金载体 -> 日报先判市场资金结构和板块扩散，再找板块内被反复买入和承接的资金载体；涨停、热榜、龙虎榜和分数只作证据，不作自动买入资格",
    "资金载体角色 -> 涨停高标、趋势容量核心、板块锚/中军、分支龙头都可观察；好股不一定每天涨停，但必须证明资金反复参与、回撤有人接、放量不崩、缩量不死",
    "唯一明日动作 -> 量化参与痕迹和价格行为确认后，还要经过反证、账户、盈亏比和时间窗口，最后只输出一个动作或观察结论",
    "条件链优先 -> 排序必须来自可见事实、合理推断、反方证据和明日动作，不用加权总分替代解释",
    "证据不足处理 -> 没有价格接受或反证解除时，不取得新增参与资格，只观察恢复条件",
    "量价四象限 -> 放量上涨强收盘看进攻，放量冲高回落看分歧，缩量回踩趋势未破等二次确认，放量破位先处理风险",
    "低位突放巨量 -> 只提高研究和观察优先级，必须等后续行情，不直接生成买入资格",
    "布鲁克斯趋势区间谱系 -> 先判强趋势/普通趋势/宽幅通道/交易区间，再决定顺势、等待还是只观察",
    "布鲁克斯后续行情确认 -> 单根K线、0轴、MA和涨停只触发观察；承接、强收盘和不快速跌回只能进入复盘和下一份日报，不能盘中生成新增参与",
    "始终入场方向 -> 错过强趋势早期买点后，只能用小仓位、同一失效线和同一风险预算参与，不用满仓追涨补偿",
    "二次入场确认 -> 更差价格常是为更高确认度付出的成本；所谓二次机会更便宜时先怀疑趋势转弱",
    "形态失败燃料 -> 失败突破、失败反转和失败回踩会套住交易者，止损和反手可能给相反方向提供动力",
    "交易者等式 -> 参与前说清成功概率、目标空间、失败损失和账户伤害，说不清只观察",
    "价格裁判 -> 资金流/指标只作辅助，价格站回强弱线才升级资格",
    "交易理由与执行锚点 -> 量能/情绪/板块/资金/辨识度/承接先给买卖资格，MA3/MA5/MA10只优化买卖点和失效线",
    "当下执行 -> 盘中只执行、取消或降风险昨晚日报已决定的动作；新增证据只能进入复盘和下一份日报判断",
    "心理时间校准 -> 未来大机会、长期价值兑现、新股首日暴涨和题材后续发酵，只能进入观察或研究，不能压迫当下动作",
    "短线当下性 -> 短线不期待遥不可及的兑现，也不赌神迹；计划可以面向未来，执行只能落在当前可验证事实",
    "MA5低于MA7弱排列 -> 先按下跌中继或弱修复观察，不给主买/补位资格；只有站回MA7、放量大阳、收在高位且强板块同步，才恢复比较资格",
    "该涨不涨 -> 时间消耗风险，降级/减仓/换样本",
    "生存优先 -> 小资金T+1先控制满仓隔夜风险",
    "数学期望 -> 低回撤和稳定复利优先于单日大盈利次数",
    "收益预期现实化 -> 日赚1%不是稳定目标，按月净值和最大回撤评估系统",
    "月度攻击目标 -> 15%-20%是阶段进攻目标，不是每日交易要求，不达标也不能用错误仓硬凑",
    "小资金盈利模式 -> 少数高质量核心机会贡献主要利润，轻仓试错、确认后加、冲高分批卖、破结构减",
    "风险处理 -> 个股3%-5%浮亏先检查买入理由，失效价破坏才处理，个股-10%是事故极限",
    "账户伤害 -> 止损看个股结构，伤害看账户本金，普通波动不能打残账户",
    "攻击频次 -> 没有防守边界的高频进攻会把收益对冲成无效波动",
    "亏损边界 -> 先避免大亏损，再追求偶尔向上大盈利",
    "收益风险不对称 -> 先承认高波动，再用仓位、窗口、做T、卖点线和失效条件让收益靠近弹性、亏损边界收敛",
    "胜率赔率 -> 胜率接近天花板时用大赚小亏和利润奔跑修复期望",
    "小资金做T纪律 -> 优先选择更正确的确认买点，不追求更便宜；做T先降风险，确认后买回",
    "做T博值率 -> 下方防守条件和上方止盈条件同时写清；没有止盈只等拉升不是博值率",
    "同股T临时2x -> 已有1x且今日目标仍是同一只票时只按同股T候选处理；强表态存活才允许临时2x，失败后卖可卖旧仓",
    "强表态失败 -> 09:30-09:35急拉只作观察；快速跌破VWAP、昨收或MA7且不能收回时，不新增并按失败样本处理",
    "尾盘卖出边界 -> 早盘买入次日尾盘卖出只适用于正常样本；失败样本接近最大亏损或跌破关键线时先处理风险",
    "2B参与确认 -> B1买参与权，B2买确认权；B2不是任务仓，没有确认就没有补足义务",
    "计划取消过滤 -> 交易计划不是仓位完成任务，而是确认、取消和降风险的筛选器；B1没赢之前B2不存在",
    "走弱不补仓 -> 走弱不是补仓理由，是取消第二笔、检查第一笔的理由",
    "态度不是仓位 -> 集合竞价买一部分已经表达态度，剩余仓位必须留给市场确认",
    "仓位跟随证据 -> 仓位是证据强度的结果，不是当天必须买够的目标；坏样本只亏B1，好样本才给B1+B2",
    "少亏复利 -> 2B法允许少赚但必须减少坏样本完整回撤；少亏不是畏手畏脚，而是长期跑赢的一部分",
    "确认后加速 -> 短线超额来自确认后加速，不来自所有样本开盘买满；失败不补，旧仓先降风险",
    "0轴不作做T买点 -> 0轴只观察动能强弱；10:10之后尤其不能因为将要突破0轴而新增买入",
    "随意时间点买入禁止 -> 三段买卖窗口外不新增主动买入；破坏时间纪律后当天只处理风险和写错题复盘",
    "做T买点贴近认错线 -> 优先等MA5回踩确认，再用MA7等失效线控制亏损边界，避免吃完整0轴到MA7下跌",
    "冲动伪装应变 -> 把观察信号错当买入资格、把盘中冲动包装成临盘应变，是反复违反0轴和时间纪律的本质",
    "从容交易人格 -> 长期赚钱的人不是没有冲动，而是不让冲动直接变成交易动作；只参与让自己从容的机会",
    "计划外盈利不正名 -> 计划外交易即使一度盈利，也不能证明当时决策正确；复盘只按事前信息、买入资格、时间窗口和亏损边界评分",
    "偏离日报重新取资格 -> 日报没有明日对象或明确不新增时，自主买入必须独立重新取得市场、板块、个股、窗口和认错线资格，不能继承原日报信用",
    "失败仓低开加仓 -> 旧仓已失败且没有独立买回确认时，低开加仓不是做T，而是亏损厌恶在证明第一笔",
    "怕卖飞不覆盖退出 -> 失败仓触发退出后，害怕卖出反弹只代表机会成本，不能取消退出；后续修复必须作为下一笔独立决策",
    "龙虎榜证据边界 -> 龙虎榜只覆盖上榜席位样本；净买不能代表全市场主力方向，不能推导榜外小额资金踩踏，净买与跌停并存时价格接受仍然失败",
    "长期叙事不续命 -> 存储、科技或其他长期产业逻辑不能给短线失败仓续命；继续持有必须由当前价格承接、板块同步和失效线重新证明",
    "盈利后失控防线 -> 连续盈利后先复核仓位、窗口、失效线和禁止清单，不把短期手感当永久实力",
    "无趣交易生存 -> 条件执行、见好就收、严格失效和看不懂就不参与，优先保护长期可执行性",
    "两笔异常停手 -> 连续两笔不符合预演或触发失效，直接停手观察股池，不用第三笔证明自己",
    "活跃资金风向标 -> 连板高度、热点宽度、活跃股梯队和高位异动群体爆发率共同判断环境",
    "强者修复再参与 -> 高位反包、V型修复和板块承接同步出现后，才从观察恢复参与",
    "市场兜底校准 -> 结果被板块修复兜底不等于决策正确；复盘先看当时条件是否满足",
    "赚钱效应退潮 -> 单边趋势道寻常，震荡退潮期降低攻击频次和预期收益",
    "震荡市短线波段 -> 连跌后只允许轻仓低吸，反弹后不再创新低、底部抬高才有波段关注意义，不把低吸扩成满仓趋势持有",
    "一九行情看图优先 -> 少数上涨多数下跌时，持仓图形优先于题材解释；图形好继续拿，图形走差抓紧降风险",
    "趋势股越跌越减 -> 针对追高且图形走弱的趋势仓；沿均线上行可持有，图形破坏反弹减亏",
    "均线执行锚点 -> MA3/MA5/MA10/MA20用于识别震荡区间的反弹、回落和趋势破坏，不替代交易理由",
    "量化看图 -> 技术图形、成交数据和消息会放大线位反应，只作执行环境不作买入理由",
    "消息归因降权 -> 除个股直接风险外，消息只确认风险，不生成买点，不替代价格量能承接和仓位判断",
    "集中大赚 -> 必须先写代价和平衡，不能把追求大赚变成无边界押注",
    "AI摩擦与知识复利 -> 消除低效摩擦后必须补上反馈机制；复利方向由接入过程决定，知识节点碰撞形成个人护城河",
    "必要认知摩擦 -> AI生成后至少复述、重写、对比或沉淀成知识节点，避免只复制结果",
    "问题定义优先 -> 先定义需要改善的决定、事实边界、完成证据和不可改变项，再提问消除关键未知，最后完成最小可验证闭环",
    "决定先于工具 -> 不从AI能做什么出发，先问哪个重要决定仍容易做错、为什么会错、怎样证明变好",
    "有效价值乘法 -> 问题重要性、定义质量、解决质量和验证可信度共同决定结果，任何一项接近零，整体价值都接近零",
    "验证失败复核 -> 先检查事实和问题定义，再修改方案；不在错误问题上继续堆叠答案",
    "交易问答知识复利 -> 盘中摩擦必须拆成价格事实、当时判断、实际偏差、可复用规则、下次动作；能影响下一次问股才算正向复利",
    "外部启发转交易规则 -> 先分原文可支持、系统化抽象、不能归因给原文，再落到市场条件、参与边界和复盘反证",
    "自以为是校准 -> 判断欲强时先回到价格事实、账户占用、亏损边界和失效条件，不用顺口类比替代可复盘字段",
    "模仿学习校准 -> 抄袭不可怕，怕的是不知道抄的重心和理念；初学先八分像拿正反馈，成熟后取三五分骨架迁移",
    "位置先于能力 -> 先判市场阶段、账户状态、持仓身份和先后手，再给参与动作",
    "线内动作 -> 主线、辨识度、承接、时间窗口、失效条件和账户承受力清楚才参与；边界外不证明自己",
    "愿望事实分离 -> 应该要拉、跌多了、逻辑没问题不能替代价格承接和失效条件",
    "同天标的复盘 -> 先排市场强度，再排账户可操作性；账户不适配不降低市场身份",
    "强弱校准字段 -> 趋势连续性、开盘主动性、分歧承接优先于便宜和做T便利",
    "强票账户不适配 -> 买不了也保留为板块锚，只是不参与当前账户比较",
    "替代票源头校准 -> 更强标的账户可买时优先更强标的，不能用好做T的弱替代覆盖",
    "去弱留强第一原则表达 -> 短线账户把资金放到当下相对强、承接清楚、失败条件可承受的对象；弱仓处理和强票参与必须分别取得资格",
    "汰弱留强 -> 资金优先留给仍被市场选择、承接和执行条件更清楚的对象；旧仓失效先处理，新机会必须独立确认",
    "旧仓新机会分离 -> 先判旧仓是否仍有持仓或做T资格，再判新机会是否更强且窗口和亏损边界清楚，最后决定资金优先级",
    "新旧仓双资格 -> 卖旧仓看旧仓是否失去持仓资格，买新仓看新仓是否取得执行资格；不能用旧仓变弱直接推出新仓满仓",
    "结构性吸血行情 -> 指数强但多数个股弱时，先承认资金集中在强主线；旧方向日内反弹不等于风格切换",
    "旧方向右侧确认 -> 超跌反弹后回落不再创新低、底部抬高，才恢复短线波段观察；继续新低只按弱反弹处理",
    "强主线内部轮动 -> AI硬件等强主线高潮后，优先找紧缺环节和新技术的内部轮动，不先假设大切换",
    "龙头资格反推 -> 涨停/T字板只是资金表态证据，必须通过板块锚、承接路径、相对强弱和可执行窗口反推；观察样本不能顶掉龙头",
    "供应链瓶颈研究 -> 先拆产业链，再定位材料、工艺、设备、认证、产能或客户锁定形成的关键瓶颈",
    "瓶颈股研究候选 -> 只提高研究优先级，不直接生成买入资格；交易动作仍回到价格承接、板块选择、账户适配和失效条件",
    "外部大神方法转本地规则 -> 先做来源保真，再做系统化抽象，不保留收益宣传或本人官方授权假设",
    "卡脖子三问 -> 先问行业扩张卡在哪里、谁控制瓶颈、市场是否已充分定价，不先问股票代码",
    "下游倒推上游瓶颈 -> 显眼龙头只作需求源，继续追材料、工艺、认证、产能、设备和上游处理能力",
    "噪音归零验证 -> 瓶颈假设、客户验证、产能兑现和财报方向未破时，不用短期评论替代证据；证据破坏就降级",
    "宏观看空微观做多 -> 总市场风险决定动作敏感度，个体赢家仍按瓶颈证据、价格承接和板块选择单独研究",
    "迹象识别链 -> 从反复出现的市场迹象提炼现象规律，再在实战中识别、验证和主动运用，不把单次巧合当规律",
    "相对优势进攻 -> 等弱方向开始掉队、强方向仍有资金扩散和核心承接时，才从观察进入参与",
    "主战场能力圈 -> 短线/超短线追求500强水平；趋势容量、机构抱团和慢推行情只求不拖后腿",
    "非主战场纪律 -> 低适配行情不扩战法，不为证明全能而新增参与",
    "正确风险 -> 小资金不是求稳回避风险，而是选择市场愿意拥抱的高辨识度风险，再用仓位、窗口、做T和卖点线压低下行",
    "辨识度优先样本 -> 优先看市场效应、成交容量、板块核心、涨停反馈、承接和收盘位置，不用便宜或好做T替代",
    "涨停位置与资金信心 -> 涨停数量看情绪，涨停位置看信心；高位承接和突破晋级说明资金愿意进攻，低位首板多更偏反弹点火",
    "资金阶段 -> 小资金允许追求高弹性，但只做市场承认的热门核心，不做随机高波动",
    "小资金优势校准 -> 小资金优势是灵活切换核心，不是频繁乱动或救错误仓",
    "AI辅助边界 -> AI负责筛核心、拦错误、做复盘，不承诺省心躺赚",
    "热门妖股 -> 价格、成交、辨识度、板块地位共同确认的核心，不是听来的故事票",
    "辨识度优先 -> 高弹性交易优先选择市场共识最强的核心标的，宁可少做不做边缘票",
    "低流动性锯齿分时 -> 锯齿分时、盘口稀疏和少数大单直线涨停只记不可复制结果，不因事后涨停提高优先级",
    "新股辨识度 -> 新股身份不是辨识度，只有盟固利/无线传媒式情绪旗帜才升级为核心",
    "趋势容错 -> 上升趋势/短期周期未破时容错高，下降趋势/周期破坏时容错低",
    "周期持有 -> 短线按博弈周期判断，周期未破可持有，周期破坏先退出",
    "买点卖点底层操作 -> MA3攻击线 / MA7分歧线 / MA10认错线 / MA20环境线",
    "MA3附近先定亏损边界 -> 跌到MA3只触发观察；未站回VWAP前宁可错过，试错必须先按账户占用和单笔伤害定义上限",
    "9:45量能异动 -> 只作提前观察和强弱排序；09:50-10:10窗口用前段利润换大跌风险过滤，未过09:50-10:10承接不提前参与",
    "主窗口不漂移 -> 09:45-09:50是前哨观察，09:50-10:10是执行窗口，10:10-10:15只复核不新增买点",
    "点位依据声明 -> 盘中买卖点必须说明来自MA组合、VWAP、开盘价、前高前低、成交密集区或形态脚本，无来源区间不作决策",
    "形态交易脚本 -> 上升趋势顺势回踩，下降趋势只做右侧确认，V/M/W/A按确认与破坏执行",
    "高位后手不追形态 -> 烂板、停顿、空中加油都不给后手追涨资格；只看次日或分歧后的重新承接",
    "三类形态处理 -> 烂板看次日强承接，停顿等放量转强，空中加油按已有仓管理；新仓等充分换手或回踩确认",
    "追涨杀跌动作中性 -> 追涨杀跌只是动作，质量取决于趋势地基、盈亏同源点、股性、时间窗口和失效线；无规则情绪动作不参与",
    "趋势地基 -> 长期趋势、平台消化、缩量回踩承接、放量不崩和板块降温后仍横住，才说明资金共识扎实",
    "盈亏同源点 -> 对了能快速脱离成本并打开空间，错了会很快跌破强弱线或结构；必须贴近认错线并先算亏损边界",
    "股性过滤 -> 涨停频率、早盘主动性、板块地位和辨识度决定资金效率；磨叽票不因形态好自动升级",
    "旱地拔葱风险 -> 无地基急拉只按情绪观察处理，不因为涨得快就追",
    "紧急止损规则 -> 收盘同破MA7/MA10、放量大跌超7%、连续3日MA3下方、MA20下拐",
    "均线下方不主动进攻 -> MA3下方不做超短进攻，MA7下方不做短线加仓，MA20下方不做主动交易",
    "成交量确认 -> 放量破位优先信风险，缩量破位必须看能否收回",
    "指数价跌量增 -> 指数或全市场大跌且两市成交额放大，优先按卖压释放、量化踩踏或出货风险处理",
    "放量杀跌局部强势 -> 只按逆势试攻或观察主攻线，等指数止跌、跌停收敛和主攻线连续承接后再恢复评估",
    "价格带风格 -> 百元股涨跌幅减低价股涨跌幅，-2pct以下低价相对抗跌，-2pct到+2pct价格带均衡，+2pct以上高价相对占优；只作局部风格",
    "创新高趋势 -> 非ST非新股非次新250日新高占全A比例；5%及以上极致扩散，2%到5%有效扩散，1%到2%扩散偏冷，0.2%到1%极低扩散，低于0.2%或新高数低于10只为扩散断层；同一低值还要看变化方向",
    "创新高用法 -> 只作资金扩散方向雷达，权重封顶；不直接生成个股买点，参与仍看趋势审美、承接、回踩质量和作废线",
    "市场情绪总状态 -> 先看盘面亏钱效应，指数大跌、跌多涨少、跌停扩散时，局部指标高潮只能写局部过热，整体高潮必须亏钱效应不重、热度扩散强、方向确认强",
    "情绪异动两日验证 -> 大众情绪剧烈波动后先写两日验证；连续实体阴线按最后一杀观察，异动后直接大阳按资金切到新线路观察",
    "超跌反弹预期 -> 跌多只给短套利预期；未出现趋势反转和资金回流前，不把反弹升级为新趋势",
    "时间窗口偏好 -> 买卖只认09:30-09:35、09:50-10:10、14:30-14:55三段；尾盘不再拆其他子窗口",
    "低位缩量横盘试龙头 -> 长期低位缩量后突放巨量/涨停/炸板，再缩量横盘后二次放量启动，才进入强势样本观察",
    "无公开题材异动 -> 只记资金提前表态假设和研究优先级，不能直接写成已知利好或无条件买点",
    "开盘核心0轴收复 -> 低开不超过-3%，09:30-09:35收复0轴并站稳分时黄线，才算开盘主动性；不新增9:40买卖窗口",
    "龙头日内转弱 -> 开盘-5%以下、跌破-3%后无近端强支撑、尾盘大幅下杀收不回、放量大跌，优先降风险",
    "特殊节点隔日确认 -> 龙头分歧日、首阴日、龙回头支撑日当天只观察，隔天开盘走强确认后才恢复参与资格",
    "市场总龙节点纪律 -> 分歧日、首阴日、龙回头支撑日只用于市场总龙；补涨龙、支线龙、龙二龙三不做这些节点",
    "周五风险 -> 周四或周五加速、周五高位博弈和周末消息不确定时，先降仓位和预期，周一再确认",
    "异动监管验证 -> 监管提示后能不大跌并继续走强，才算龙头韧性；低于预期则降级",
    "低开-5%处理 -> 龙头任何时候到-5%都极度小心，当天不开新仓，拉高先处理，真想参与等隔天走强",
    "龙头急跌后急拉 -> 急跌后可等下一分钟急拉修复；若再转弱跌破-3%且无近端支撑，先降风险",
    "加速风险 -> +7%以上或冲板按加速观察，周四周五加速更偏兑现风险，温和放量上涨更健康",
    "核买核卖博弈 -> 核买后马上核卖或反向急拉急跌时，比较回撤和反击比例，空方吃掉三分之二要小心",
    "龙头恐惧处理 -> 恐惧来自畏高和大亏；用低仓位试错、确认后加仓和利润壁垒替代空想勇敢",
    "龙头心态纪律 -> 利润放大贪婪时继续跟随市场；看不懂就离场，不因利润垫硬格局，接受龙头结束时亏一笔",
    "上影线趋势警惕 -> 连续上影线说明做多被压制，次日破MA5先离场观察",
    "上影线身份分层 -> 高辨识度核心长上影先观察修复，跟风票长上影优先处理，低辨识度票长上影不参与",
    "经验规则校准 -> 避坑规则必须带重新参与条件，否则避坑会变成错过",
    "启动板 -> 短线触发转趋势观察仓，必须记录启动逻辑、持股规则、破坏退出",
    "趋势持股短板 -> 卖出原因可复盘，区分风险信号和情绪信号",
    "盈亏同审 -> 已卖样本和持仓样本按同一套卖出原因、持股理由、失效条件、3/5/10日验证复盘",
    "利润奔跑与亏损边界 -> 有趋势资格的盈利仓不因小波动提前卖，失效仓不因亏损扩大继续死拿",
    "换仓错题 -> 先证明旧仓失效，再证明新仓更强，最后证明新仓风险能承受",
    "亏损后切换 -> 当天默认暂停新方向，禁止用更高波动标的找回本金",
    "充值补亏陷阱 -> 亏损失效仓不能靠充值加仓摊低成本，充值只能用于下一笔独立机会",
    "明日交易计划 -> 账户状态、持仓处理、时间窗口、大盘剧本、板块锚点、候选预演、禁止清单",
    "无计划新方向 -> 未写入前一晚计划且未通过四重确认，盘中默认没有满仓买入资格",
    "日报前置风险快照 -> 日报生成先对持仓、候选、明日主买和补位全量查询公告/互动问答/投资者关系风险，盘中问股只做刷新补查",
    "问答风险源配置 -> Tushare irm_qa_sh/irm_qa_sz优先，默认近10日窗口，INVESTOR_QA_ENDPOINT_URL兜底，候选比较前合并到stock_risk_map",
    "盘中问股前置条件 -> 先查公告/互动问答/投资者关系风险，再看主线/承接，最后才用MA/VWAP定执行",
    "盘中点位依据 -> 每个买卖点必须说明均线角色、VWAP、开盘价、前高前低、成交密集区或形态脚本",
    "公告风险处理 -> 减持、强制执行、司法冻结、质押风险会让均线支撑降级为观察位",
    "炒作预期降维 -> 问董秘/互动易澄清命中当前上涨发动机时加重扣分，未命中当前主线/候选理由/概念标签时只提示；强核心观察，非核心或弱势不进极度看好",
    "当前上涨发动机自动推导 -> 从市场主线、候选理由、概念标签、选股宝关联板块和热门原因提取current_driver_tags，再判断澄清是否命中",
    "候选质量条件链 -> 先看市场和板块，再看角色、风险、恢复条件和动作上限；条件链决定最多能做什么",
    "今日总决策面板 -> 市场情绪、账户后台任务负担、今日新增上限、持仓优先动作、主买对象、补位对象、禁止动作和忽略清单先于单票排序",
    "候选主表 -> 当前持仓、可卖数量、不可卖数量、仓位性质、账户状态、计划仓位档、实际仓位、仓位偏离、周期身份、选股质量、买点质量、风险项、成本项、动作上限、持仓动作、新开仓动作、恢复条件、取关条件、最晚复核",
    "账户状态 -> 实际可买/实际不可买；只决定账户是否参与，不改变市场核心、池内身份或周期身份",
    "仓位表达 -> 计划仓位档记录0/50/100策略意图，实际仓位记录一手颗粒度后的账户落点，仓位偏离说明低配或超配",
    "半仓颗粒度 -> 一手实际占用40%-60%仍按50%档，不升满仓也不降观察；决策看档位，账户看实际",
    "选股买点拆分 -> 好票高成本保护选股资格但不追高；差票低成本的MA/VWAP只作已有仓处理参考",
    "后台任务负担 -> 未处理风险仓会占用注意力，先处理持仓风险再看新增机会，高负担时不新增参与",
    "动作五层 -> 主买、补位、核心观察、修复观察、不参与；持仓动作和新开仓动作分开输出",
    "盘中问股继承 -> 先读前一晚动作层级和今日新增上限；不参与不能直升主买或补位，观察类恢复条件命中也只进入复盘和下一份日报判断",
    "复盘校准 -> 记录当时判断、实际走势、买点出现、用户偏离、错误归因和样本保护结果；不因单个收益结果自动调权重",
    "误判归因顺序 -> 先分随机结果、决策层缺陷、AI摩擦；价格强弱和账户约束读错归决策层，话术太绝归AI摩擦，不因单次涨跌改规则",
    "容量强度锚 -> 高成交高热度板块核心保留为强弱参照；账户占用过高可不参与，但不能从最终观察视野消失",
    "样本保护 -> 规则变更必须同时检查核心机会、差票低成本和好票高成本样本，不能为修边角破坏大机会",
    "恢复取关复核 -> 每个观察样本必须写恢复条件、取关条件和最晚复核时间，避免观察变成后台任务",
    "禁止清单 -> 不该做什么优先级高于想买什么，先拦错再谈进攻",
    "来源保真 -> 区分原文可支持、系统化抽象、不能归因给原文",
    "变更伴随文档 -> 每次需求变更和每次生成日报时，同步生成AGENTS.md、flow.md、testing.md、readme.md四个伴随文件；日报伴随目录随reports/replay路径落盘，不写项目根目录；必须能复盘边界、流程、验证和入口",
    "新股周期 -> 市场周期、新股扩散、首日情绪、C阶段承接、情绪出口地位",
    "新股样本 -> 盟固利是弱市投机宣泄；无线传媒是强修复情绪出口；历史相似不能替代当前承接验证",
    "新股年景推演 -> 2015-2025未见连续两年小年；小年后先按大年假设观察，仍要用月度连续性、扩散和标志性样本验证",
    "2026新股基线 -> 2025小年后按大年假设；2026-04-13启动后先按年底前持续活跃观察，但日历推演不能替代单票承接",
    "板块节奏 -> 量化环境下先看板块路径和资金选择，再看单一龙头定价",
    "窄池子进攻 -> 指数强但上涨家数弱时，不按普涨处理，先看资金集中选择哪些板块路径",
    "板块反弹质量 -> 板块指数走坏时反弹先按卖点或减风险；板块指数仍好且窗口、承接和亏损边界清楚时才提高参与质量",
    "主动被动分层 -> 盘中被资金主动做多后被指数下跌带回的板块，次日指数修复时优先观察重新进攻；主动冲高回落则按走坏处理",
    "冰点接冰点与值博率 -> 连续预期反弹却继续跌不能否认，但连续压缩会改变值博率；提前写清反弹来时做什么",
    "反弹三分类 -> 主动带动反弹看参与，跟随指数反弹看减风险，熟悉资产修复看持续承接；板块高潮碰上指数深V时先写共振待确认",
    "水池九宫格 -> 全市场资金水池被板块网格化，结构性行情先看资金灌入哪个板块格子，再看个股属于主线、短线还是边角",
    "先选板块 -> 指数强不等于普涨；先判被资金选择的板块路径和资金柱高度，再评估个股角色、承接、价格和账户",
    "六层趋势推导 -> 市场和市场趋势先限定参与上限；趋势板块完成跨日持续、分歧承接、内部扩散和竞争方向对照后，再比较板块生态、板块中趋势个股和个股价格确认",
    "局部领先仓位 -> 偏弱市场中的完整局部趋势最多给B1参与权；B2仍等更广泛赚钱效应、个股价格和账户条件确认，局部个股强势不能反向证明上层改善",
    "边角标的 -> 没站在被资金选择的格子里时，不因轮动自动取得参与资格；先承认位置不占优，再决定是否继续观察",
    "量化仍在 -> 板块成交占比维持或扩张、板块宽度扩散、核心承接稳定、竞争方向掉队",
    "量化离场 -> 成交占比回落、后排掉队、核心跌回VWAP或关键均线，三项共振时先退出",
    "中军持续性 -> 板块上涨后中军次日继续放量上涨或横住，才说明大资金仍在；缩量下跌时板块延续降级",
    "名字辨识度 -> 股票名称能承接题材记忆只算热度加分，必须叠加板块路径、中军和个股承接",
    "板块高标反馈 -> 小弟和高标不能大面积负反馈；一字板高标跳水伤板块，板块强而龙头弱也要降级",
    "抱团环境 -> 普跌环境更容易抱团市场总龙，普涨环境会降低龙头辨识度和单票溢价",
    "风格切换 -> 主升后震荡分歧先看轮动、回流、题材活跃和连板晋级率",
    "主线战术资源 -> 科技线可以从主攻点降为牵制点；业绩线、轮动线和低位趋势线只要走势活跃且板块逻辑共振，就要同权比较",
    "业绩趋势共振 -> 业绩超预期不是买点；业绩、板块趋势、价格结构和资金扩散同时成立，才提高观察质量",
    "风格切换载体 -> 主线真空期的强势样本不是标准答案，但最终0%后必须复核它是孤立情绪还是带出扩散承接",
    "赛道题材 -> 赛道看产业持续性，题材看概念催化，二者没有好坏但执行节奏不同",
    "板块叙事迁移 -> 表层行业标签要服从当日资金叙事，汽车零部件/电机在机器人语境下按人形机器人辅助判断",
    "龙头回头复核 -> 低位反馈不能替代龙头顶住压力；龙头二次确认和低位/中位反馈同时出现，才记录为市场继续投票",
    "鱼尾后排风险 -> 加速末端只看核心承接；补涨和后排只能作反馈，承接散掉先杀后排",
    "早信不是早买 -> 龙头或分支二次发力只提高观察优先级；买入资格仍看固定交易窗口、板块同步、个股承接、亏损边界和失效条件",
    "无人问津定义 -> 核心已经给出资金信号但板块多数载体未充分反应，不是纯下跌、便宜或没涨过",
    "鱼身位置 -> 只参与信号确认后到人声鼎沸前的中段；先涨者转弱、补涨扩散或权重拉指数时主动降风险",
    "科技震荡 -> 总体调整中只做聚焦参与，快进快出，低于预期先处理",
    "科技支线容量条件 -> 容量参考线随当前成交额分布校准，还要看科技成交、扩散和核心承接",
    "注意力发酵节点 -> 产业逻辑被集中讨论且走势仍在初期，才按支线波段观察",
    "紧缺叙事 -> 支线催化优先看主线环节供需紧张，但不能替代价格承接",
    "市场结构判断 -> 指数与真实赚钱效应、成交扩散、轮动性质、老主线疲态和题材新鲜度共同决定明日节奏",
    "低频聚焦 -> 指数强但上涨家数弱、成交集中、对立方向反弹或老主线疲态时，只保留主线核心，不从旧方向强行扩散候选",
    "外盘主线传导复核 -> 外盘默认噪音；海外同链定价、亚洲确认、A股映射、板块扩散和核心承接完整后才进入T+1复核",
    "资金载体错配 -> 叙事、核心锚、弹性载体和参与资金不在同一周期时，不能用统一持股剧本",
    "线路代表 -> 彩蛋和候选只代表资金可能切换的线路，爆发后顺着同线找龙2、龙3，不把名单当买入名单",
    "新题材早信/不信 -> 真新题材只在早期主动性和第一执行窗口提高参与质量，后手只观察或等分歧条件",
    "中枢 -> 结构区间、上沿、下沿、中轴、离开方向、回抽确认",
    "背驰 -> 动能衰减、转折风险、承接验证",
]

DATED_FIELD_MAPPINGS = [
    {
        "knowledge_id": "research.enterprise-valuation-price-dual-cycle",
        "text": "企业估值与价格执行双周期 -> 企业前提决定研究价值，估值位置决定是否值得等待，当前价格证据决定能否参与，仓位身份决定旧交易如何处理；长期机会只能进入新的T0评估",
    },
    {
        "knowledge_id": "market.new-high-core-trend-anchor",
        "text": "核心新高趋势锚 -> 全市场新高宽度、板块新高群和少数核心新高分开解释；核心新高不承诺次日延续，价格接受区必须按目标日行情复算",
    },
    {
        "knowledge_id": "market.rotation-focus-carrier-separation",
        "text": "轮动后聚焦 -> 普遍修复转向分化时只跟踪1至2个反复获跨日资金反馈的方向；核心锚、20cm弹性载体和情绪后排分周期，高切低不自动产生资格",
    },
    {
        "knowledge_id": "market.auction-delayed-sell-pressure-bayesian",
        "text": "竞价未充分定价与延迟卖盘 -> 已知利空、竞价反应有限且开盘后立即下跌时，把竞价覆盖不足和开盘后条件式卖盘作为优先工作假设；可复用机制提供方向性更新，独立样本和事前预测继续校准，不确认量化或机构身份",
    },
    {
        "knowledge_id": "market.polarization-negative-alliance-energy",
        "text": "共同排斥与双峰聚集 -> 同质性网络可能先把稀疏边缘点连接成双群聚外观和局部虚假共识；只有同一量尺下出现两个局部峰和中间低谷，才称样本双峰；再由中间层收缩、价格、成交和跨日反馈共同支持，才提高为行为或市场双峰，极化能量不等于判断正确或参与资格",
    },
    {
        "knowledge_id": "market.august-hot-stock-double-cluster-migration",
        "text": "8月热门股双群聚与动态迁移 -> 18份热门榜呈持续核心端与动态冲击端的双群聚外观，端点角色相对稳定但成员随事件和板块迁移；全市场两日形态未确认稳定双峰，不识别参与者身份，也不产生参与资格",
    },
]

REPORT_BOUNDARIES = [
    "原文不直接进入日报主链",
    "MACD只能作为辅助",
    "不把理论长文搬进日报",
    "只输出字段化结论和行动边界",
    "Wiki口径边界 -> LLM Wiki沉淀统一输出口径，运行代码生成final_target_resolution，报告模块只消费该结果不各自重算标的",
    "用户可见输出不用旧工程口径，改用资格/条件/可做/参与/不参与",
]

DAILY_DISCIPLINE_LINES = [
    "去弱留强是短线执行表达：卖旧仓看旧仓资格，买新仓看新仓资格；不能用FOMO把两笔判断合成一次满仓替换。",
    "FOMO 是外部价格刺激被自己接住后的情绪，不是执行资格；卖出后第一天因反包、后悔或怕踏空想买回，默认不执行，只能收盘后重新进入 T0 评估。",
    "反包先批改情绪反应，不直接批改前一日信息集；正确动作出现亏损结果，仍按可控小亏和纪律成本复盘。",
    "必卖日里，反抽、0轴、VWAP和开盘价修复先看作旧仓退出流动性；价格只决定卖得舒服还是狼狈，不重新决定卖不卖。",
    "Ta-Te账户日序表必须区分历史路径、今日报告和明日执行：Ta最远，Tb/Tc是前两段，Td是报告日，Te是明日执行日；明日标的为空时，Te按账户事实写旧仓独立动作、已确认无旧仓等待B1资格或持仓待确认。",
    "显式明日空仓是账户归零指令：次日不买新股，集合竞价卖清全部可卖旧仓，成交后账户仓位为0且不做T；未成交继续尽早卖，未清完不能称空仓。",
    "节奏复位不新增和延后确认不新增只解释候选复核，不改变最终0%动作；T+1强弱只能进入批改和下一份日报。",
    "日报不是每天预测一个股；先判断是否有可参与节拍，没有买入资格就0%不参与；B1只买参与权，B2等待确认。",
]

WRITE_BOUNDARIES = [
    "稳定知识写入 LLM Wiki",
    "一次性教训写入反思",
    "skill 只写行为契约",
    "service/code 写运行逻辑",
    "外部资料 -> 先来源保真归档，再沉淀知识节点",
    "知识节点 -> 写清适用场景、不适用场景、来源与证据、反证或待核实",
    "本地检索/RAG -> 只负责找材料，不替代节点判断",
]

DATA_SOURCE_POLICY = [
    "fresh daily generation uses Tushare-first",
    "PostgreSQL facts are the durable report and replay source",
    "akshare/iwencai are fallback only",
]

PUBLISH_POLICY = [
    "daily report runtime writes reports, report companion docs, snapshots, and PostgreSQL facts only",
    "retired frontend/static publish paths are not part of report generation",
]

KNOWLEDGE_COMPOUNDING_CANDIDATES = [
    {
        "related_nodes": ["AI摩擦与知识复利", "判断样本与市场演变"],
        "new_insight": "判断样本是日报里的反馈机制，用来把 AI 省掉的认知摩擦补回来。",
        "status": "待确认",
        "action": "只进入知识复利候选，不自动写入正式 wiki，不改变交易动作。",
    },
    {
        "related_nodes": ["价格行为与能量框架", "判断样本与市场演变"],
        "new_insight": "反弹回落后不再创新低、底部慢慢抬高，才有短线波段关注意义。",
        "status": "已入库",
        "action": "已写入价格行为节点，后续用来区分弱反弹和可跟踪波段，不改变交易动作。",
    }
]

PROCESS_FLOWS = [
    """选股形态审美 ASCII 流程图
[数据输入]
  |
  +--> Tushare-first日K: fetch_recent_price_bars(code, target_date, lookback_days=120)
  |       -> 写入 recent_bars
  |
  +--> 候选来源: candidates / watchlist / abnormal_watch_map / dragon_stocks / zt_pool_by_sector
  |
  +--> 近25日历史重点观察
  |       过程观察25日跟踪表 / 明日极度看好近25日跟踪表 / 重点观察历史回测表
  |       表头统一: 观察位窗口 / 观察位质量
  |       历史标准动作必须注明不作为明日新增参与依据
  |       _query_extreme_conviction_mention_rows_for_tracking -> recent_extreme_conviction_mentions
  |
  +--> 个股资料: stock_full_info / volume_anomalies / stock_risk_map / xuangubao_data
  |
  +--> 市场主线: exit_analysis / sector_snapshot / mainline_name
  v
[candidate_bundle_runtime.py]
  |
  +--> recent_extreme_conviction_mentions 补入候选复核源
  +--> 补齐价格、板块、风险和日K
  +--> _enrich_candidate_with_recent_bars -> recent_bars
  v
[build_extreme_conviction_groups]
  |
  +--> build_extreme_conviction_list -> 当前观察样本进入明日执行观察样本
  |
  +--> 价格与风险初筛
  +--> _build_trend_aesthetic_review
  |       +--> 有120日日K: MA3/MA5/MA10/MA20、MA20斜率、20日区间位置、高低点变化、最大回撤
  |       +--> 日K不足: 使用pattern_text辅助，结论保守观察
  |       +--> 历史好形态但当前承接转弱: shape_repair_pool / 形态待修复池
  |       +--> 龙回头但A杀或弱反抽未修复: dragon_rebound_watch_pool / 龙回头观察池
  |       +--> 明确破坏: A杀/放量下杀/弱反抽/高低点下移/MA20下方且收不回 -> 候选观察或取关淘汰
  +--> selection_shape_review
  |       -> 形态名称、通过状态、关注点、回避项、理由、指标、动作
  +--> final_risk_review
  |       -> 公告风险、连续长上影未修复、跌破卖点线收不回
  +--> leader_speed_profile / common_selection_check
  |       -> 速度档、买卖线、昨日持筹者、明日新买盘、主线资金、量化动量
  v
[明日极度看好比较]
  |
  +--> 非0%且资格成立: 明日主买1只 + 明日补位1只
  |
  +--> 历史好形态但当前承接转弱: 形态待修复池，重新站回短中线承接后再评估，继续走坏取关淘汰
  |
  +--> 龙回头但A杀或弱反抽未修复: 龙回头观察池，A杀未修复前不进正式名单，继续走坏取关淘汰
  |
  +--> 0%不参与 / 唯一对象暂无 / 只观察资格
          -> 主买和补位统一降为候选观察
          -> 上证缠论、明日执行计划、明日抉择同向只观察""",
    """最终对象统一输出 ASCII 流程图
[原始候选与板块证据]
  |
  +--> 板块锚反推: 先选资金最愿意反复回看的强对象
  |
  +--> 小账户资金取舍: 比较旧仓处理 / 新开仓 / 先处理旧仓后新开仓 / 等待
  |
  v
[final_target_resolution]
  |
  +--> new_entry_target: 新开仓对象
  +--> existing_position_target: 旧仓处理对象
  +--> tradable_proxy_target: 小资金可交易替代表达
  +--> watch_target: 观察对象
  +--> process_target: ASCII过程对象
  +--> display_target: 明日唯一动作或观察对象
  |
  v
[报告前台]
  -> 只消费final_target_resolution，不各自重算标的""",
    """供应链瓶颈研究 ASCII 流程图
[主题/产业]
  |
  +--> 拆产业链: 上游原料 -> 核心材料 -> 设备/工艺 -> 制造封装 -> 测试认证 -> 客户应用
  |
  +--> 下游倒推: 显眼龙头/需求源 -> 平台/模块 -> 激光器/芯片 -> 衬底/材料 -> 上游处理
  |
  +--> 找瓶颈层: 材料稀缺 / 工艺良率 / 设备交期 / 客户认证 / 产能爬坡 / 地缘约束
  |
  +--> 列供应商: 全球关键供应商 -> A股直接映射 -> A股间接映射
  |
  +--> 反方验证: 替代技术 / 扩产节奏 / 客户验证 / 收入兑现 / 流动性 / 稀释 / 地缘 / 估值
  |
  v
[日报翻译]
  -> 只生成研究线索、板块锚或候选比较字段
  -> 不直接生成买入资格
  -> 交易动作仍看价格承接、板块选择、账户适配、固定交易窗口和失效条件""",
]

REPORT_DIGEST_TEXT = (
    "载体错配先判周期角度与幅度价格是裁判资金流和指标只作辅助"
    "消息只确认风险不生成买点卖点底层操作板块节奏优先"
    "MA只做执行锚点该涨不涨降级"
    "低回撤和稳定复利优先日赚1%不是稳定目标月度15%-20%非每日要求"
    "小资金靠少数高质量核心机会轻仓确认后加冲高分批卖破结构减"
    "3%-5%浮亏先检查买入理由结构破坏才处理个股-10%事故极限"
    "计划仓位管意图实际仓位管落账户不能被普通波动打残"
    "局部强势只按逆势试攻攻击频次服从亏损边界"
    "短线当下不赌未来先避免大亏再追求大赚"
    "收益风险不对称收益靠近弹性亏损边界收敛胜率难绝对统治时靠赔率"
    "做T先确认不贪低"
    "T博值防守止盈"
    "0轴禁买观非资冲非变"
    "盈停修"
    "市场兜底不等于决策正确风险选高辨识度用策略压下行"
    "同天样本先强度后账户买不了不降级强票可买不用弱替代"
    "汰弱留强新旧"
    "MA5<MA7先弱"
    "结构吸血主线旧反弹非切换"
    "轮动找紧缺"
    "T字先反推"
    "供应链先拆瓶颈再验不可替代研究线索不直接生成买入资格"
    "三问倒推上游"
    "噪音归零看财报"
    "宏空微多找赢家"
    "震荡市连跌轻仓低吸、反弹卖回一九行情看图优先"
    "底抬高看波段"
    "题材降权图形走差抓紧降风险源配到stock_risk_map"
    "趋势股图形走弱越跌越减持强制执行让均线支撑降级"
    "MA组合只做执行锚点"
    "指数强家数弱按窄池子量化仍在看占比宽度核心承接"
    "水池九宫格先选板块"
    "占比回落后排掉队核心跌回VWAP或关键均线先退出"
    "迹象到规律再到实战运用弱方向掉队强方向扩散承接才参与"
    "周一追周五源周二不正名"
    "涨停数量看情绪位置看信心高位承接才进攻低位首板偏反弹"
    "短线超短主战场追求500强核心开盘核心"
    "非主战场不拖后腿不扩战法上影线按身份分层"
    "非0%且资格成立才给明日主买1只补位1只0%无唯一对象只观察历史表统一观察位窗口"
    "上证缠论计划抉择同向只观察速度档共同选择对子整数只作锚点"
    "顶部冲不过先止盈底部VWAP承接试错"
    "反包先按兑现点位说明MA/VWAP/开盘价/前高低/密集区/形态"
    "问股先查公告风险取消主买补位资格"
    "趋势审美看120日日K选股形态看呼吸感蛇形走位"
    "A杀放量下杀反抽不过关键线高低点下移只观察"
    "小资金高弹性只做热门核心辨识度优先小资金优势灵活切换核心AI筛核心拦错误做复盘"
    "低流动性锯齿涨停不升格"
    "MA3/MA7/MA10/MA20外部启发先做来源保真再落字段判断欲强先回价格账户亏损边界失效条件"
    "位置先于能力线内动作边界外不证明自己愿望不替代承接失效条件"
    "V/M/W/A按确认与破坏执行烂板停顿空中加油不追等重新承接"
    "紧急止损规则放量大跌超7%成交量确认指数价跌量增先防踩踏"
    "情绪总状态先看盘面亏钱效应局部指标高潮只写局部过热"
    "情绪异动后看两日验证超跌反弹只按短套利"
    "低位横盘突放量再缩量二次启动纳入强势样本"
    "无公开题材异动只记资金表态"
    "低开不超-3%收复0轴站稳黄线才算主动不新增0940窗口"
    "特殊节点隔日确认市场总龙才做分歧首阴龙回头"
    "周五和加速先防风险监管后不大跌才算韧性"
    "-5%当天不开新仓急跌等下一分钟急拉修复"
    "核买核卖看三分之二力量老龙未死不做新龙"
    "低仓试错利润壁垒克服畏高恐惧看不懂离场不靠利润垫硬格局"
    "接受龙头结束亏一笔"
    "中军次日放量或横住验证板块延续名字辨识度只作热度加分"
    "高标小弟大面积负反馈降级普跌抱团普涨降辨识度"
    "鱼尾只看核心不追后排彩蛋是线路代表不是买入名单"
    "连续上影破MA5先离场"
    "避坑规则带重新参与条件换仓先证旧仓失效、新仓更强、风险能承受"
    "亏损仓不靠充值加仓摊低成本前夜计划先定账户状态和禁止清单"
    "不可买仍在池只观察不参与今日比较无计划新方向盘中无满仓资格条件可做参与"
    "每个买卖点说明点位依据固定交易窗口条件普通结构看09:50-10:10窗口"
    "买卖窗口0930-0935/0950-1010/1430-1455失效价和单笔-5%底线"
)


def _existing_source_paths(root: Path = ROOT) -> List[str]:
    return [path for path in SOURCE_PATHS if (root / path).exists()]


def _knowledge_available_on(entry: Mapping[str, object], query_date: str) -> bool:
    available_from = str(entry.get("available_from") or "").strip()
    if not available_from:
        return True
    return is_iso_calendar_date(query_date) and available_from <= query_date


def _effective_knowledge_index(query_date: str) -> list[Mapping[str, object]]:
    return [entry for entry in KNOWLEDGE_INDEX if _knowledge_available_on(entry, query_date)]


def _knowledge_availability_date(target_date: str, query_date: str) -> str:
    dates = []
    for value in (target_date, query_date):
        normalized = str(value or "").strip()
        if normalized and is_iso_calendar_date(normalized):
            dates.append(normalized)
    if dates:
        return min(dates)
    if not str(target_date or "").strip() and not str(query_date or "").strip():
        return datetime.now(_SHANGHAI_TZ).date().isoformat()
    return ""


def _effective_source_paths(entries: list[Mapping[str, object]]) -> list[str]:
    dated_paths = {
        str(entry.get("source_path") or "").strip()
        for entry in KNOWLEDGE_INDEX
        if str(entry.get("available_from") or "").strip()
    }
    active_paths = {
        str(entry.get("source_path") or "").strip()
        for entry in entries
    }
    paths = [
        path
        for path in SOURCE_PATHS
        if path not in dated_paths or path in active_paths
    ]
    active_ids = {
        str(entry.get("id") or entry.get("knowledge_id") or "").strip()
        for entry in entries
    }
    paths.extend(
        str(item["path"])
        for item in DATED_SOURCE_PATHS
        if str(item["knowledge_id"]) in active_ids
    )
    return list(dict.fromkeys(paths))


def _effective_field_mappings(entries: list[Mapping[str, object]]) -> list[str]:
    active_ids = {
        str(entry.get("id") or entry.get("knowledge_id") or "").strip()
        for entry in entries
    }
    mappings = list(FIELD_MAPPINGS)
    mappings.extend(
        str(item["text"])
        for item in DATED_FIELD_MAPPINGS
        if str(item["knowledge_id"]) in active_ids
    )
    return mappings


def _manifest_list(value: object) -> list[object]:
    return list(value) if isinstance(value, list) else []


def _manifest_string_list(value: object) -> list[str]:
    return [str(item) for item in _manifest_list(value)]


def _filter_manifest_by_availability(
    manifest: Mapping[str, object],
    availability_date: str,
) -> dict[str, object]:
    """Remove dated entries that were not available at the requested boundary."""
    compiled = deepcopy(dict(manifest))
    raw_entries = compiled.get("entries")
    if not isinstance(raw_entries, list):
        return compiled

    retained_entries: list[object] = []
    excluded_source_paths: set[str] = set()
    retained_source_paths: set[str] = set()
    excluded_knowledge_ids: set[str] = set()
    retained_knowledge_ids: set[str] = set()
    filtered = False
    for entry in raw_entries:
        if not isinstance(entry, Mapping) or _knowledge_available_on(entry, availability_date):
            retained_entries.append(entry)
            if isinstance(entry, Mapping):
                knowledge_id = str(entry.get("knowledge_id") or entry.get("id") or "").strip()
                if knowledge_id:
                    retained_knowledge_ids.add(knowledge_id)
                source_ref = entry.get("source_ref")
                if isinstance(source_ref, Mapping):
                    source_path = str(source_ref.get("path") or "").strip()
                    if source_path:
                        retained_source_paths.add(source_path)
            continue
        filtered = True
        knowledge_id = str(entry.get("knowledge_id") or entry.get("id") or "").strip()
        if knowledge_id:
            excluded_knowledge_ids.add(knowledge_id)
        source_ref = entry.get("source_ref")
        if isinstance(source_ref, Mapping):
            source_path = str(source_ref.get("path") or "").strip()
            if source_path:
                excluded_source_paths.add(source_path)

    if not filtered:
        return compiled

    excluded_source_paths.update(
        str(item.get("path") or "").strip()
        for item in DATED_SOURCE_PATHS
        if str(item.get("knowledge_id") or "").strip() in excluded_knowledge_ids
    )
    excluded_source_paths.difference_update(retained_source_paths)
    excluded_knowledge_ids.difference_update(retained_knowledge_ids)
    compiled["entries"] = retained_entries

    sources = compiled.get("sources")
    if isinstance(sources, list):
        compiled["sources"] = [
            source
            for source in sources
            if not isinstance(source, Mapping)
            or str(source.get("path") or "").strip() not in excluded_source_paths
        ]

    for field in (
        "expected_source_paths",
        "available_source_paths",
        "missing_source_paths",
        "invalid_source_paths",
    ):
        values = compiled.get(field)
        if isinstance(values, list):
            compiled[field] = [
                value
                for value in values
                if str(value or "").strip() not in excluded_source_paths
            ]

    filtered_sources = compiled.get("sources")
    if isinstance(filtered_sources, list) and all(
        isinstance(source, Mapping) for source in filtered_sources
    ):
        compiled["available_source_paths"] = [
            str(source.get("path") or "").strip()
            for source in filtered_sources
            if source.get("availability") == "available"
        ]
        compiled["missing_source_paths"] = [
            str(source.get("path") or "").strip()
            for source in filtered_sources
            if source.get("availability") == "missing"
        ]
        compiled["invalid_source_paths"] = [
            str(source.get("path") or "").strip()
            for source in filtered_sources
            if source.get("availability") == "invalid"
        ]

    declared_errors = _manifest_string_list(compiled.get("errors"))
    invalid_paths = _manifest_string_list(compiled.get("invalid_source_paths"))
    missing_paths = _manifest_string_list(compiled.get("missing_source_paths"))
    warnings = _manifest_string_list(compiled.get("warnings"))
    if str(manifest.get("availability") or "").strip() == "invalid" or declared_errors or invalid_paths:
        compiled["availability"] = "invalid"
    elif missing_paths:
        compiled["availability"] = "missing_sources"
    elif warnings:
        compiled["availability"] = "partial"
    else:
        compiled["availability"] = "ready"
    compiled["manifest_hash"] = stable_json_hash(
        compiled,
        excluded_keys={"manifest_hash"},
    )
    return compiled


def build_llm_wiki_context(
    *,
    target_date: str = "",
    query_date: str = "",
    manifest: Mapping[str, object] | None = None,
    source_root: Path | str | None = None,
) -> Dict[str, object]:
    root = Path(source_root) if source_root is not None else ROOT
    normalized_query_date = str(query_date or "").strip()
    availability_date = _knowledge_availability_date(target_date, normalized_query_date)
    effective_index = _effective_knowledge_index(availability_date)
    effective_source_paths = _effective_source_paths(effective_index)
    compiled_manifest = (
        _filter_manifest_by_availability(manifest, availability_date)
        if isinstance(manifest, Mapping)
        else build_knowledge_manifest(
            effective_index,
            root=root,
            wiki_version=WIKI_VERSION,
            language=WIKI_LANGUAGE,
            expected_source_paths=effective_source_paths,
        )
    )
    validation_errors = list(
        dict.fromkeys(
            [
                *validate_knowledge_manifest(compiled_manifest),
                *validate_knowledge_manifest_sources(compiled_manifest, root=root),
            ]
        )
    )
    if validation_errors:
        compiled_manifest["availability"] = "invalid"
        compiled_manifest["errors"] = list(
            dict.fromkeys(
                [*_manifest_string_list(compiled_manifest.get("errors")), *validation_errors]
            )
        )
        compiled_manifest["warnings"] = list(
            dict.fromkeys(
                [*_manifest_string_list(compiled_manifest.get("warnings")), *validation_errors]
            )
        )
        compiled_manifest["manifest_hash"] = stable_json_hash(
            compiled_manifest,
            excluded_keys={"manifest_hash"},
        )
    availability = str(compiled_manifest.get("availability") or "invalid")
    return {
        "version": WIKI_VERSION,
        "source": WIKI_SOURCE,
        "language": WIKI_LANGUAGE,
        "target_date": str(target_date or "").strip(),
        "query_date": str(query_date or "").strip(),
        "manifest": compiled_manifest,
        "manifest_hash": str(compiled_manifest.get("manifest_hash") or ""),
        "expected_source_paths": (
            _manifest_string_list(compiled_manifest.get("expected_source_paths"))
            or list(effective_source_paths)
        ),
        "available_source_paths": _manifest_string_list(
            compiled_manifest.get("available_source_paths")
        ),
        "missing_source_paths": _manifest_string_list(
            compiled_manifest.get("missing_source_paths")
        ),
        "availability": availability,
        "confidence": llm_wiki_confidence_for_availability(availability),
        "warnings": _manifest_string_list(compiled_manifest.get("warnings")),
        "source_paths": _manifest_string_list(compiled_manifest.get("available_source_paths")),
        "field_mappings": _effective_field_mappings(effective_index),
        "report_boundaries": list(REPORT_BOUNDARIES),
        "daily_discipline_lines": list(DAILY_DISCIPLINE_LINES),
        "write_boundaries": list(WRITE_BOUNDARIES),
        "data_source_policy": list(DATA_SOURCE_POLICY),
        "publish_policy": list(PUBLISH_POLICY),
        "knowledge_compounding_candidates": [dict(item) for item in KNOWLEDGE_COMPOUNDING_CANDIDATES],
        "process_flows": list(PROCESS_FLOWS),
        "report_digest_text": REPORT_DIGEST_TEXT,
    }


def _is_complete_trace_hit(hit: object) -> bool:
    if not isinstance(hit, Mapping):
        return False
    required_text = (
        "hit_id",
        "knowledge_id",
        "prior",
        "source_path",
        "title",
        "impact",
        "report_slot",
        "confidence",
        "decision_effect",
        "decision_scope",
    )
    required_lists = (
        "triggered_by",
        "matched_conditions",
        "matched_topics",
        "matched_fact_paths",
        "matched_fact_sources",
        "used_for",
        "not_used_for",
    )
    if any(not str(hit.get(field) or "").strip() for field in required_text):
        return False
    if any(not isinstance(hit.get(field), list) for field in required_lists):
        return False
    if not isinstance(hit.get("rank"), int) or isinstance(hit.get("rank"), bool):
        return False
    if not isinstance(hit.get("score"), (int, float)) or isinstance(hit.get("score"), bool):
        return False
    source_ref = hit.get("source_ref")
    return bool(
        isinstance(source_ref, Mapping)
        and is_sha256(source_ref.get("content_hash"))
        and hit.get("decision_scope") == "explanation_only"
    )


def _trace_hit_matches_manifest(hit: Mapping[str, object], entry: Mapping[str, object]) -> bool:
    hit_source_ref = hit.get("source_ref")
    entry_source_ref = entry.get("source_ref")
    report_slots = [str(item) for item in entry.get("report_slots") or []]
    if not isinstance(hit_source_ref, Mapping) or not isinstance(entry_source_ref, Mapping):
        return False
    return bool(
        entry.get("available") is True
        and str(hit.get("knowledge_id") or "") == str(entry.get("knowledge_id") or "")
        and str(hit.get("prior") or "") == str(entry.get("prior") or "")
        and str(hit.get("title") or "") == str(entry.get("title") or "")
        and str(hit.get("source_path") or "") == str(entry_source_ref.get("path") or "")
        and str(hit.get("impact") or "") == str(entry.get("decision_effect") or "")
        and str(hit.get("decision_effect") or "") == str(entry.get("decision_effect") or "")
        and str(hit.get("decision_scope") or "") == str(entry.get("decision_scope") or "")
        and str(hit.get("confidence") or "") == str(entry.get("confidence") or "")
        and str(hit.get("report_slot") or "") == (report_slots[0] if report_slots else "")
        and dict(hit_source_ref) == dict(entry_source_ref)
    )


def _trace_fact_sources_are_complete(trace: Mapping[str, object]) -> bool:
    facts_source = str(trace.get("facts_source") or "").strip()
    fact_sources = trace.get("fact_sources")
    hits = trace.get("hits")
    if facts_source not in {"derived", "explicit"} or not isinstance(fact_sources, Mapping):
        return False
    if not isinstance(hits, list):
        return False

    normalized_sources: Dict[str, Dict[str, str]] = {}
    for raw_path, raw_source_ref in fact_sources.items():
        path = str(raw_path or "").strip()
        if path not in EXPLICIT_FACT_PATHS or not isinstance(raw_source_ref, Mapping):
            return False
        expected_input_path = (
            f"knowledge_hit_facts.{path}"
            if facts_source == "explicit"
            else path
        )
        source = str(raw_source_ref.get("source") or "").strip()
        input_path = str(raw_source_ref.get("input_path") or "").strip()
        if source != facts_source or input_path != expected_input_path:
            return False
        normalized_sources[path] = {
            "source": source,
            "input_path": input_path,
        }

    for hit in hits:
        if not isinstance(hit, Mapping):
            return False
        matched_paths = hit.get("matched_fact_paths")
        matched_sources = hit.get("matched_fact_sources")
        if not isinstance(matched_paths, list) or not isinstance(matched_sources, list):
            return False
        if any(not isinstance(path, str) or path not in normalized_sources for path in matched_paths):
            return False
        expected_sources = [
            {"path": path, **normalized_sources[path]}
            for path in matched_paths
        ]
        if matched_sources != expected_sources:
            return False
    return True


def _trace_knowledge_is_available_on(
    hits: list[object],
    manifest_entries: Mapping[str, Mapping[str, object]],
    availability_date: str,
) -> bool:
    if not is_iso_calendar_date(availability_date):
        return False
    for hit in hits:
        if not isinstance(hit, Mapping):
            return False
        entry = manifest_entries.get(str(hit.get("knowledge_id") or "").strip())
        if not isinstance(entry, Mapping):
            return False
        available_from = str(entry.get("available_from") or "").strip()
        if available_from and (
            not is_iso_calendar_date(available_from)
            or available_from > availability_date
        ):
            return False
    return True


def _is_complete_frozen_trace(
    existing: Mapping[str, object],
    trace: Mapping[str, object],
    *,
    target_date: str,
    query_date: str = "",
) -> bool:
    manifest = existing.get("manifest")
    hits = trace.get("hits")
    warnings = trace.get("warnings")
    if not isinstance(manifest, Mapping) or validate_knowledge_manifest(manifest):
        return False
    manifest_entries = {
        str(entry.get("knowledge_id") or "").strip(): entry
        for entry in manifest.get("entries") or []
        if isinstance(entry, Mapping)
    }
    if (
        not isinstance(hits, list)
        or any(not isinstance(hit, Mapping) for hit in hits)
        or not _trace_fact_sources_are_complete(trace)
    ):
        return False
    if not all(
        _is_complete_trace_hit(hit)
        and _trace_hit_matches_manifest(
            hit,
            manifest_entries.get(str(hit.get("knowledge_id") or "").strip(), {}),
        )
        for hit in hits
    ):
        return False
    ranks = [int(hit.get("rank")) for hit in hits]
    hit_ids = [str(hit.get("hit_id") or "").strip() for hit in hits]
    knowledge_ids = [str(hit.get("knowledge_id") or "").strip() for hit in hits]
    if (
        ranks != list(range(1, len(hits) + 1))
        or hit_ids != [f"kh-{rank:03d}" for rank in ranks]
        or len(hit_ids) != len(set(hit_ids))
        or len(knowledge_ids) != len(set(knowledge_ids))
    ):
        return False
    if not isinstance(warnings, list):
        return False
    trace_hash = str(trace.get("trace_hash") or "").strip()
    trace_availability = str(trace.get("availability") or "").strip()
    manifest_availability = str(manifest.get("availability") or "").strip()
    outer_availability = str(existing.get("availability") or manifest_availability).strip()
    existing_availability = outer_availability
    if (
        outer_availability == "source_changed"
        and str(existing.get("artifact_origin") or "").strip() == "frozen_trace"
    ):
        existing_availability = str(existing.get("frozen_availability") or "").strip()
    expected_target_date = str(target_date or "")
    existing_target_date = str(existing.get("target_date") or "")
    trace_target_date = str(trace.get("target_date") or "")
    existing_query_date = str(existing.get("query_date") or "")
    trace_query_date = str(trace.get("query_date") or "")
    requested_query_date = str(query_date or "")
    normalized_requested_query_date = requested_query_date.strip()
    requested_query_date_is_valid = not requested_query_date or (
        requested_query_date == normalized_requested_query_date
        and is_iso_calendar_date(normalized_requested_query_date)
    )
    availability_dates = [
        value
        for value in (
            expected_target_date,
            existing_query_date,
            trace_query_date,
            normalized_requested_query_date,
        )
        if value
    ]
    availability_date = min(availability_dates) if availability_dates else ""
    trace_not_used_for = trace.get("not_used_for")
    decision_boundary_is_supported = isinstance(trace_not_used_for, list) and trace_not_used_for in (
        list(DECISION_FIELDS_EXCLUDED_FROM_KNOWLEDGE),
        list(_LEGACY_DECISION_FIELDS_EXCLUDED_FROM_KNOWLEDGE),
    )
    return bool(
        trace.get("schema_version") == "knowledge_trace.v1"
        and is_iso_calendar_date(expected_target_date)
        and trace_target_date == expected_target_date
        and existing_target_date == expected_target_date
        and is_iso_calendar_date(trace_target_date)
        and is_iso_calendar_date(existing_target_date)
        and trace_query_date == existing_query_date
        and is_iso_calendar_date(trace_query_date)
        and is_iso_calendar_date(existing_query_date)
        and requested_query_date_is_valid
        and str(trace.get("scenario") or "").strip()
        and str(trace.get("facts_source") or "").strip()
        and trace.get("decision_scope") == "explanation_only"
        and decision_boundary_is_supported
        and trace_availability in VALID_MANIFEST_AVAILABILITIES
        and trace_availability == manifest_availability
        and trace_availability == existing_availability
        and is_sha256(trace.get("manifest_hash"))
        and is_sha256(trace.get("facts_hash"))
        and is_sha256(trace_hash)
        and trace.get("manifest_hash") == existing.get("manifest_hash")
        and trace.get("manifest_hash") == manifest.get("manifest_hash")
        and _trace_knowledge_is_available_on(
            hits,
            manifest_entries,
            availability_date,
        )
        and trace_hash == stable_json_hash(trace, excluded_keys={"trace_hash"})
    )


def is_complete_frozen_llm_wiki_context(
    frozen_context: Mapping[str, object] | None,
    *,
    target_date: str,
    query_date: str = "",
) -> bool:
    """Return whether a fresh context contains a complete replay-safe trace."""
    if not isinstance(frozen_context, Mapping):
        return False
    trace = frozen_context.get("knowledge_trace")
    if not isinstance(trace, Mapping):
        return False
    return _is_complete_frozen_trace(
        frozen_context,
        trace,
        target_date=str(target_date or ""),
        query_date=str(query_date or ""),
    )


def is_complete_fresh_llm_wiki_context(
    fresh_context: Mapping[str, object] | None,
    *,
    target_date: str,
    source_root: Path | str | None = None,
) -> bool:
    """Require a replay-safe trace whose declared source hashes match current bytes."""
    if not is_complete_frozen_llm_wiki_context(
        fresh_context,
        target_date=target_date,
    ):
        return False
    manifest = fresh_context.get("manifest") if isinstance(fresh_context, Mapping) else None
    if not isinstance(manifest, Mapping):
        return False
    root = Path(source_root) if source_root is not None else ROOT
    return not validate_knowledge_manifest_sources(manifest, root=root)


def build_replay_llm_wiki_context(
    frozen_context: Mapping[str, object] | None,
    *,
    target_date: str,
    query_date: str = "",
    source_root: Path | str | None = None,
) -> Dict[str, object]:
    """Reuse an intact target-date trace or return an explicit historical gap."""
    requested_target_date = str(target_date or "")
    target_date = requested_target_date.strip()
    query_date = (
        str(query_date or "").strip()
        or datetime.now(_SHANGHAI_TZ).date().isoformat()
    )
    existing = deepcopy(dict(frozen_context)) if isinstance(frozen_context, Mapping) else {}
    trace = existing.get("knowledge_trace") if isinstance(existing.get("knowledge_trace"), Mapping) else {}
    trace = deepcopy(dict(trace)) if isinstance(trace, Mapping) else {}
    trace_target_date = str(trace.get("target_date") or "").strip()
    trace_is_frozen = is_complete_frozen_llm_wiki_context(
        existing,
        target_date=requested_target_date,
        query_date=query_date,
    )
    if trace_is_frozen:
        existing["analysis_mode"] = "replay"
        existing["artifact_origin"] = "frozen_trace"
        existing["replay_knowledge_status"] = "frozen"
        existing["target_date"] = target_date
        existing["knowledge_hits"] = deepcopy(list(trace.get("hits") or []))
        frozen_availability = str(trace.get("availability") or "invalid").strip()
        frozen_confidence = llm_wiki_confidence_for_availability(frozen_availability)
        source_change_warning = "当前经验库来源与冻结版本不同，需要按来源复核"
        existing["availability"] = frozen_availability
        existing["confidence"] = frozen_confidence
        existing["review_confidence"] = frozen_confidence
        existing.pop("frozen_availability", None)
        existing.pop("frozen_confidence", None)
        existing["warnings"] = [
            item
            for item in existing.get("warnings") or []
            if str(item) != source_change_warning
        ]
        source_issues = validate_knowledge_manifest_sources(
            existing.get("manifest") or {},
            root=Path(source_root) if source_root is not None else ROOT,
        )
        source_diagnostics = {
            "status": "changed" if source_issues else "matched",
            "issues": source_issues,
        }
        existing["replay_source_diagnostics"] = source_diagnostics
        if source_issues:
            existing["frozen_availability"] = frozen_availability
            existing["frozen_confidence"] = frozen_confidence
            existing["availability"] = "source_changed"
            current_confidence = llm_wiki_confidence_for_availability("source_changed")
            existing["confidence"] = current_confidence
            existing["review_confidence"] = current_confidence
            source_diagnostics["review_availability"] = "source_changed"
            source_diagnostics["review_confidence"] = current_confidence
            existing["warnings"] = list(
                dict.fromkeys([*(existing.get("warnings") or []), source_change_warning])
            )
        return existing

    if trace and trace_target_date and trace_target_date != target_date:
        warning = "冻结知识引用日期与目标交易日不一致；未使用当前经验库补写"
    elif trace:
        warning = "冻结知识引用不完整；未使用当前经验库补写"
    else:
        warning = "当时知识引用缺失；未使用当前经验库补写"
    missing_trace = {
        "schema_version": "knowledge_trace.v1",
        "target_date": target_date,
        "query_date": query_date,
        "scenario": "daily_report",
        "manifest_hash": "",
        "facts_hash": "",
        "facts_source": "historical_snapshot",
        "fact_sources": {},
        "decision_scope": "explanation_only",
        "not_used_for": list(DECISION_FIELDS_EXCLUDED_FROM_KNOWLEDGE),
        "availability": "historical_trace_missing",
        "warnings": [warning],
        "hits": [],
    }
    missing_trace["trace_hash"] = stable_json_hash(missing_trace)
    return {
        "version": "",
        "source": "llm_wiki",
        "language": WIKI_LANGUAGE,
        "target_date": target_date,
        "query_date": query_date,
        "analysis_mode": "replay",
        "artifact_origin": "missing",
        "replay_knowledge_status": "missing",
        "availability": "historical_trace_missing",
        "confidence": llm_wiki_confidence_for_availability("historical_trace_missing"),
        "review_confidence": llm_wiki_confidence_for_availability(
            "historical_trace_missing"
        ),
        "warnings": [warning],
        "knowledge_hits": [],
        "knowledge_trace": missing_trace,
        "field_mappings": [],
        "daily_discipline_lines": [],
        "knowledge_compounding_candidates": [],
        "process_flows": [],
    }


__all__ = [
    "build_llm_wiki_context",
    "build_replay_llm_wiki_context",
    "is_complete_fresh_llm_wiki_context",
    "is_complete_frozen_llm_wiki_context",
    "llm_wiki_confidence_for_availability",
]
