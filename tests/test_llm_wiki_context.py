import copy
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _m(*parts):
    return "".join(parts)

from knowledge.llm_wiki_context import (
    build_llm_wiki_context,
    build_replay_llm_wiki_context,
    is_complete_frozen_llm_wiki_context,
    llm_wiki_confidence_for_availability,
)
from knowledge.llm_wiki_manifest import build_knowledge_manifest, stable_json_hash
from knowledge.llm_wiki_router import KNOWLEDGE_INDEX, route_llm_wiki_knowledge_trace


def _frozen_context(target_date="2026-07-16"):
    context = build_llm_wiki_context(target_date=target_date, query_date="2026-07-17")
    trace = route_llm_wiki_knowledge_trace(
        {
            "account": {"status": "实际不可买"},
            "candidate": {"identity": "市场核心"},
        },
        manifest=context["manifest"],
        target_date=target_date,
        query_date="2026-07-17",
    )
    context["knowledge_trace"] = trace
    context["knowledge_hits"] = list(trace["hits"])
    return context


class LlmWikiContextTest(unittest.TestCase):
    def test_build_llm_wiki_context_materializes_compact_chinese_nodes(self):
        context = build_llm_wiki_context()

        self.assertEqual(context["version"], "2026-07-17")
        self.assertEqual(context["source"], "llm_wiki")
        self.assertEqual(context["language"], "zh-CN")
        self.assertEqual(context["manifest"]["schema_version"], "knowledge_manifest.v1")
        self.assertEqual(context["manifest_hash"], context["manifest"]["manifest_hash"])
        self.assertEqual(len(context["manifest"]["entries"]), len(KNOWLEDGE_INDEX))
        self.assertEqual(context["availability"], context["manifest"]["availability"])
        self.assertIn("wiki/交易思想/缠论体系.md", context["source_paths"])
        self.assertIn("wiki/交易思想/价格行为与能量框架.md", context["source_paths"])
        self.assertIn("wiki/交易思想/布鲁克斯价格行为趋势.md", context["source_paths"])
        self.assertIn("wiki/交易思想/反伪精确第一性原理.md", context["source_paths"])
        self.assertIn("wiki/交易思想/启动板与趋势持股短板.md", context["source_paths"])
        self.assertIn("wiki/交易思想/极度看好参与时机.md", context["source_paths"])
        self.assertIn("wiki/交易思想/交易错题本.md", context["source_paths"])
        self.assertIn("wiki/交易思想/做T与风险控制.md", context["source_paths"])
        self.assertIn("wiki/交易思想/新股周期与市场情绪.md", context["source_paths"])
        self.assertIn("wiki/交易思想/扣分系统与动作分层.md", context["source_paths"])
        self.assertIn("wiki/交易思想/实际账户情况.md", context["source_paths"])
        self.assertEqual(context["source_paths"].count("wiki/交易思想/扣分系统与动作分层.md"), 1)
        self.assertIn("wiki/交易思想/判断样本与市场演变.md", context["source_paths"])
        self.assertIn("wiki/交易思想/AI摩擦与知识复利.md", context["source_paths"])
        self.assertIn("wiki/板块补充/供应链瓶颈研究法.md", context["source_paths"])
        self.assertIn("wiki/板块补充/板块中枢与主线延续.md", context["source_paths"])
        self.assertIn("wiki/资料库/时空乐道0704早信与周期.md", context["source_paths"])
        self.assertIn("wiki/交易思想/日报术语契约.md", context["source_paths"])
        self.assertIn("wiki/运行契约/日报数据源契约.md", context["source_paths"])
        self.assertIn("wiki/运行契约/LLM Wiki维护与路由契约.md", context["source_paths"])
        self.assertNotIn("wiki/运行契约/前端发布契约.md", context["source_paths"])
        self.assertIn("日线结构中枢定环境 -> 固定交易窗口条件 -> 失效价和单笔-5%底线", context["field_mappings"])
        self.assertIn("普通结构观察 -> 09:50-10:10窗口；强核心快路径 -> 09:30-09:35竞价表态、开盘前几分钟或回封", context["field_mappings"])
        self.assertIn("参与时机 -> open_core开盘核心 / ten_confirm 09:50-10:10窗口 / tail_exception尾盘14:30-14:55例外 / no_trade不交易", context["field_mappings"])
        self.assertIn("买卖窗口期 -> 只在09:30-09:35、09:50-10:10、14:30-14:55三段处理买卖；窗口外不新增买卖动作，只等待下一窗口或处理既定风险", context["field_mappings"])
        self.assertIn("Ta-Te账户日序表 -> Ta最远复盘日，Tb/Tc是前两段路径，Td是报告日，Te是明日执行日；Te只承接昨晚决定的参与、取消或旧仓降风险", context["field_mappings"])
        self.assertIn("上一日明日标的继承 -> 上一份日报写出的明日标的只保留待成交路径；用户输入或成交事实确认后才计入1x/B1，未确认前按0x且不新增B2", context["field_mappings"])
        self.assertIn("1x/2x盘中交叉 -> 每个明日标的默认1x满仓信号；2x只来自旧仓1x未卖且新买1x成交的盘中重叠，不是单票开盘前自动加仓", context["field_mappings"])
        self.assertIn("空仓日旧仓处理 -> 明日标的为空时没有新买对象，继承旧仓只按旧仓盈亏比和失效条件处理，越早回到空仓越符合空仓结论", context["field_mappings"])
        self.assertIn("统一来源 -> 日报写入decision-ledger planned_participation，报告和复盘只消费同一份结构化计划，不各自重算", context["field_mappings"])
        self.assertIn("极度看好复盘 -> 日报生成时用行情表回写participation_review，封死买不到不算收益命中", context["field_mappings"])
        self.assertIn("明日主买对象 -> 非0%且参与资格成立时给1只主买和1只补位；最终0%时统一降为候选观察", context["field_mappings"])
        self.assertIn("前台收口 -> 0%不参与、唯一对象暂无或只给观察资格时，所有明日动作面板只写观察，不写主买补位或新增参与", context["field_mappings"])
        self.assertIn("反预测崇拜与应对剧本 -> 日报不是预测节拍，而是判断有没有可参与动作；没有明确买入资格时0%不参与也是有效结论", context["field_mappings"])
        self.assertIn("第一动作分层 -> 第一根阳线、指数翻红或板块回暖只给观察信号或B1参与权，不直接给B2确认权", context["field_mappings"])
        self.assertIn("量化行为博弈 -> 日报同时识别市场动作和散户一致行为陷阱，避免把踏空焦虑、回本卖出、小赚止盈或阳线追后排当成交易理由", context["field_mappings"])
        self.assertIn("狙击手推导顺序 -> 先判退潮，再取候选，再做最终风险复核，再判龙头速度档和买卖线，最后比较共同选择一致性", context["field_mappings"])
        self.assertIn("龙头速度档 -> 极致加速看MA3/MA5，高弹性强趋势看MA5/MA10，大容量趋势看MA10/MA20", context["field_mappings"])
        self.assertIn("共同选择一致性 -> 昨日持筹者不急卖、明日新买盘愿意接、主线资金仍有理由选择", context["field_mappings"])
        self.assertIn("心理价位与量化锚点 -> 对子数、整数位、前高前低、VWAP、MA和成交密集区只作价格锚点，不作独立买入理由", context["field_mappings"])
        self.assertIn("隐藏买卖盘 -> 顶部锚点冲不过按隐藏卖盘和止盈观察，底部锚点必须站回VWAP并在09:50-10:10窗口承接稳定才允许试错", context["field_mappings"])
        self.assertIn("量化共同选择 -> 昨日持筹者、明日新买盘、主线资金、量化动量四方一致后才提高参与质量", context["field_mappings"])
        self.assertIn("高潮反包 -> 高潮后反包优先按先手兑现点，放量吃掉压力并回踩不破才恢复候选", context["field_mappings"])
        self.assertIn("太极实业跌停N字样本 -> 入选不是因为跌停本身，而是上一日报明日标的继承、半导体/AI硬件关注、容量成交热度、关键价带和结构性外部事件共同触发次日验证", context["field_mappings"])
        self.assertIn("最终风险复核 -> 公告风险、连续长上影未修复、跌破对应卖点线收不回，取消主买和补位资格", context["field_mappings"])
        self.assertIn("趋势审美复核 -> 明日极度看好先看近120日日K，上升趋势/平台震荡/缩量回踩有承接才保留；A杀/放量下杀/反抽不过关键线/高低点下移只观察", context["field_mappings"])
        self.assertIn("选股形态审美 -> 先看120日日K的呼吸感、蛇形走位、重心上移、平台消化和缩量回踩；A杀、破位弱反抽、放量下杀不参与", context["field_mappings"])
        self.assertIn("图形美学 -> 假底先按反抽看；真正的进攻雏形通常是小K线、缩量横盘、重心上移、靠近前高，最终等阳包阴或突破阳线确认", context["field_mappings"])
        self.assertIn("形态待修复池 -> 历史好形态或趋势比价链样本当前承接转弱但未A杀时保留跟踪；重新站回短中线承接后再评估，继续走坏取关淘汰", context["field_mappings"])
        self.assertIn("龙回头观察池 -> 历史辨识度仍在但A杀或弱反抽未修复时单独观察；不进正式名单，重新站回短中线承接后再评估，继续走坏取关淘汰", context["field_mappings"])
        self.assertIn("日报固定附录 -> 必须渲染附录A：明日极度看好列表、附录A：龙回头观察池，让个股名单可快速定位", context["field_mappings"])
        self.assertIn("选股形态流程 -> 数据源到120日日K复核、历史三表复盘、明日极度看好比较；最终0%时上证缠论、明日执行计划、明日抉择统一只观察", context["field_mappings"])
        self.assertIn("历史观察表头 -> 重点观察25日、明日极度看好近25日、历史回测表统一使用观察位窗口/观察位质量", context["field_mappings"])
        self.assertIn("价格裁判 -> 资金流/指标只作辅助，价格站回强弱线才升级资格", context["field_mappings"])
        self.assertIn("交易理由与执行锚点 -> 量能/情绪/板块/资金/辨识度/承接先给买卖资格，MA3/MA5/MA10只优化买卖点和失效线", context["field_mappings"])
        self.assertIn("该涨不涨 -> 时间消耗风险，降级/减仓/换样本", context["field_mappings"])
        self.assertIn("生存优先 -> 小资金T+1先控制满仓隔夜风险", context["field_mappings"])
        self.assertIn("数学期望 -> 低回撤和稳定复利优先于单日大盈利次数", context["field_mappings"])
        self.assertIn("收益预期现实化 -> 日赚1%不是稳定目标，按月净值和最大回撤评估系统", context["field_mappings"])
        self.assertIn("月度攻击目标 -> 15%-20%是阶段进攻目标，不是每日交易要求，不达标也不能用错误仓硬凑", context["field_mappings"])
        self.assertIn("小资金盈利模式 -> 少数高质量核心机会贡献主要利润，轻仓试错、确认后加、冲高分批卖、破结构减", context["field_mappings"])
        self.assertIn("风险处理 -> 个股3%-5%浮亏先检查买入理由，失效价破坏才处理，个股-10%是事故极限", context["field_mappings"])
        self.assertIn("账户伤害 -> 止损看个股结构，伤害看账户本金，普通波动不能打残账户", context["field_mappings"])
        self.assertIn("攻击频次 -> 没有防守边界的高频进攻会把收益对冲成无效波动", context["field_mappings"])
        self.assertIn("亏损边界 -> 先避免大亏损，再追求偶尔向上大盈利", context["field_mappings"])
        self.assertIn("收益风险不对称 -> 先承认高波动，再用仓位、窗口、做T、卖点线和失效条件让收益靠近弹性、亏损边界收敛", context["field_mappings"])
        self.assertIn("胜率赔率 -> 胜率接近天花板时用大赚小亏和利润奔跑修复期望", context["field_mappings"])
        self.assertIn("小资金做T纪律 -> 优先选择更正确的确认买点，不追求更便宜；做T先降风险，确认后买回", context["field_mappings"])
        self.assertIn("做T博值率 -> 下方防守条件和上方止盈条件同时写清；没有止盈只等拉升不是博值率", context["field_mappings"])
        self.assertIn("市场兜底校准 -> 结果被板块修复兜底不等于决策正确；复盘先看当时条件是否满足", context["field_mappings"])
        self.assertIn("赚钱效应退潮 -> 单边趋势道寻常，震荡退潮期降低攻击频次和预期收益", context["field_mappings"])
        self.assertIn("震荡市短线波段 -> 连跌后只允许轻仓低吸，反弹后不再创新低、底部抬高才有波段关注意义，不把低吸扩成满仓趋势持有", context["field_mappings"])
        self.assertIn("一九行情看图优先 -> 少数上涨多数下跌时，持仓图形优先于题材解释；图形好继续拿，图形走差抓紧降风险", context["field_mappings"])
        self.assertIn("趋势股越跌越减 -> 针对追高且图形走弱的趋势仓；沿均线上行可持有，图形破坏反弹减亏", context["field_mappings"])
        self.assertIn("均线执行锚点 -> MA3/MA5/MA10/MA20用于识别震荡区间的反弹、回落和趋势破坏，不替代交易理由", context["field_mappings"])
        self.assertIn("量化看图 -> 技术图形、成交数据和消息会放大线位反应，只作执行环境不作买入理由", context["field_mappings"])
        self.assertIn("消息归因降权 -> 除个股直接风险外，消息只确认风险，不生成买点，不替代价格量能承接和仓位判断", context["field_mappings"])
        self.assertIn("集中大赚 -> 必须先写代价和平衡，不能把追求大赚变成无边界押注", context["field_mappings"])
        self.assertIn("AI摩擦与知识复利 -> 消除低效摩擦后必须补上反馈机制；复利方向由接入过程决定，知识节点碰撞形成个人护城河", context["field_mappings"])
        self.assertIn("必要认知摩擦 -> AI生成后至少复述、重写、对比或沉淀成知识节点，避免只复制结果", context["field_mappings"])
        self.assertIn("交易问答知识复利 -> 盘中摩擦必须拆成价格事实、当时判断、实际偏差、可复用规则、下次动作；能影响下一次问股才算正向复利", context["field_mappings"])
        self.assertIn("同天标的复盘 -> 先排市场强度，再排账户可操作性；账户不适配不降低市场身份", context["field_mappings"])
        self.assertIn("强弱校准字段 -> 趋势连续性、开盘主动性、分歧承接优先于便宜和做T便利", context["field_mappings"])
        self.assertIn("强票账户不适配 -> 买不了也保留为板块锚，只是不参与当前账户比较", context["field_mappings"])
        self.assertIn("替代票源头校准 -> 更强标的账户可买时优先更强标的，不能用好做T的弱替代覆盖", context["field_mappings"])
        self.assertIn("去弱留强第一原则表达 -> 短线账户把资金放到当下相对强、承接清楚、失败条件可承受的对象；弱仓处理和强票参与必须分别取得资格", context["field_mappings"])
        self.assertIn("新旧仓双资格 -> 卖旧仓看旧仓是否失去持仓资格，买新仓看新仓是否取得执行资格；不能用旧仓变弱直接推出新仓满仓", context["field_mappings"])
        self.assertIn("板块节奏 -> 量化环境下先看板块路径和资金选择，再看单一龙头定价", context["field_mappings"])
        self.assertIn("窄池子进攻 -> 指数强但上涨家数弱时，不按普涨处理，先看资金集中选择哪些板块路径", context["field_mappings"])
        self.assertIn("量化仍在 -> 板块成交占比维持或扩张、板块宽度扩散、核心承接稳定、竞争方向掉队", context["field_mappings"])
        self.assertIn("量化离场 -> 成交占比回落、后排掉队、核心跌回VWAP或关键均线，三项共振时先退出", context["field_mappings"])
        self.assertIn("迹象识别链 -> 从反复出现的市场迹象提炼现象规律，再在实战中识别、验证和主动运用，不把单次巧合当规律", context["field_mappings"])
        self.assertIn("相对优势进攻 -> 等弱方向开始掉队、强方向仍有资金扩散和核心承接时，才从观察进入参与", context["field_mappings"])
        self.assertIn("主战场能力圈 -> 短线/超短线追求500强水平；趋势容量、机构抱团和慢推行情只求不拖后腿", context["field_mappings"])
        self.assertIn("非主战场纪律 -> 低适配行情不扩战法，不为证明全能而新增参与", context["field_mappings"])
        self.assertIn("正确风险 -> 小资金不是求稳回避风险，而是选择市场愿意拥抱的高辨识度风险，再用仓位、窗口、做T和卖点线压低下行", context["field_mappings"])
        self.assertIn("辨识度优先样本 -> 优先看市场效应、成交容量、板块核心、涨停反馈、承接和收盘位置，不用便宜或好做T替代", context["field_mappings"])
        self.assertIn("涨停位置与资金信心 -> 涨停数量看情绪，涨停位置看信心；高位承接和突破晋级说明资金愿意进攻，低位首板多更偏反弹点火", context["field_mappings"])
        self.assertIn("上影线身份分层 -> 高辨识度核心长上影先观察修复，跟风票长上影优先处理，低辨识度票长上影不参与", context["field_mappings"])
        self.assertIn("资金阶段 -> 小资金允许追求高弹性，但只做市场承认的热门核心，不做随机高波动", context["field_mappings"])
        self.assertIn("小资金优势校准 -> 小资金优势是灵活切换核心，不是频繁乱动或救错误仓", context["field_mappings"])
        self.assertIn("AI辅助边界 -> AI负责筛核心、拦错误、做复盘，不承诺省心躺赚", context["field_mappings"])
        self.assertIn("热门妖股 -> 价格、成交、辨识度、板块地位共同确认的核心，不是听来的故事票", context["field_mappings"])
        self.assertIn("辨识度优先 -> 高弹性交易优先选择市场共识最强的核心标的，宁可少做不做边缘票", context["field_mappings"])
        self.assertIn("低流动性锯齿分时 -> 锯齿分时、盘口稀疏和少数大单直线涨停只记不可复制结果，不因事后涨停提高优先级", context["field_mappings"])
        self.assertIn("新股辨识度 -> 新股身份不是辨识度，只有盟固利/无线传媒式情绪旗帜才升级为核心", context["field_mappings"])
        self.assertIn("趋势容错 -> 上升趋势/短期周期未破时容错高，下降趋势/周期破坏时容错低", context["field_mappings"])
        self.assertIn("周期持有 -> 短线按博弈周期判断，周期未破可持有，周期破坏先退出", context["field_mappings"])
        self.assertIn("买点卖点底层操作 -> MA3攻击线 / MA7分歧线 / MA10认错线 / MA20环境线", context["field_mappings"])
        self.assertIn("MA3附近先定亏损边界 -> 跌到MA3只触发观察；未站回VWAP前宁可错过，试错必须先按账户占用和单笔伤害定义上限", context["field_mappings"])
        self.assertIn("9:45量能异动 -> 只作提前观察和强弱排序；09:50-10:10窗口用前段利润换大跌风险过滤，未过09:50-10:10承接不提前参与", context["field_mappings"])
        self.assertIn("主窗口不漂移 -> 09:45-09:50是前哨观察，09:50-10:10是执行窗口，10:10-10:15只复核不新增买点", context["field_mappings"])
        self.assertIn("点位依据声明 -> 盘中买卖点必须说明来自MA组合、VWAP、开盘价、前高前低、成交密集区或形态脚本，无来源区间不作决策", context["field_mappings"])
        self.assertIn("形态交易脚本 -> 上升趋势顺势回踩，下降趋势只做右侧确认，V/M/W/A按确认与破坏执行", context["field_mappings"])
        self.assertIn("高位后手不追形态 -> 烂板、停顿、空中加油都不给后手追涨资格；只看次日或分歧后的重新承接", context["field_mappings"])
        self.assertIn("三类形态处理 -> 烂板看次日强承接，停顿等放量转强，空中加油按已有仓管理；新仓等充分换手或回踩确认", context["field_mappings"])
        self.assertIn("追涨杀跌动作中性 -> 追涨杀跌只是动作，质量取决于趋势地基、盈亏同源点、股性、时间窗口和失效线；无规则情绪动作不参与", context["field_mappings"])
        self.assertIn("趋势地基 -> 长期趋势、平台消化、缩量回踩承接、放量不崩和板块降温后仍横住，才说明资金共识扎实", context["field_mappings"])
        self.assertIn("盈亏同源点 -> 对了能快速脱离成本并打开空间，错了会很快跌破强弱线或结构；必须贴近认错线并先算亏损边界", context["field_mappings"])
        self.assertIn("股性过滤 -> 涨停频率、早盘主动性、板块地位和辨识度决定资金效率；磨叽票不因形态好自动升级", context["field_mappings"])
        self.assertIn("紧急止损规则 -> 收盘同破MA7/MA10、放量大跌超7%、连续3日MA3下方、MA20下拐", context["field_mappings"])
        self.assertIn("成交量确认 -> 放量破位优先信风险，缩量破位必须看能否收回", context["field_mappings"])
        self.assertIn("指数价跌量增 -> 指数或全市场大跌且两市成交额放大，优先按卖压释放、量化踩踏或出货风险处理", context["field_mappings"])
        self.assertIn("放量杀跌局部强势 -> 只按逆势试攻或观察主攻线，等指数止跌、跌停收敛和主攻线连续承接后再恢复评估", context["field_mappings"])
        self.assertIn("价格带风格 -> 百元股涨跌幅减低价股涨跌幅，-2pct以下低价相对抗跌，-2pct到+2pct价格带均衡，+2pct以上高价相对占优；只作局部风格", context["field_mappings"])
        self.assertIn("创新高趋势 -> 非ST非新股非次新250日新高占全A比例，2%以下趋势扩散偏冷，2%到5%趋势扩散震荡，5%以上趋势扩散偏热；不单独代表整体市场温度", context["field_mappings"])
        self.assertIn("创新高用法 -> 只作资金扩散方向雷达，权重封顶；不直接生成个股买点，参与仍看趋势审美、承接、回踩质量和作废线", context["field_mappings"])
        self.assertIn("市场情绪总状态 -> 先看盘面亏钱效应，指数大跌、跌多涨少、跌停扩散时，局部指标高潮只能写局部过热，整体高潮必须亏钱效应不重、热度扩散强、方向确认强", context["field_mappings"])
        self.assertIn("时间窗口偏好 -> 买卖只认09:30-09:35、09:50-10:10、14:30-14:55三段；尾盘不再拆其他子窗口", context["field_mappings"])
        self.assertIn("低位缩量横盘试龙头 -> 长期低位缩量后突放巨量/涨停/炸板，再缩量横盘后二次放量启动，才进入强势样本观察", context["field_mappings"])
        self.assertIn("无公开题材异动 -> 只记资金提前表态假设和研究优先级，不能直接写成已知利好或无条件买点", context["field_mappings"])
        self.assertIn("开盘核心0轴收复 -> 低开不超过-3%，09:30-09:35收复0轴并站稳分时黄线，才算开盘主动性；不新增9:40买卖窗口", context["field_mappings"])
        self.assertIn("龙头日内转弱 -> 开盘-5%以下、跌破-3%后无近端强支撑、尾盘大幅下杀收不回、放量大跌，优先降风险", context["field_mappings"])
        self.assertIn("特殊节点隔日确认 -> 龙头分歧日、首阴日、龙回头支撑日当天只观察，隔天开盘走强确认后才恢复参与资格", context["field_mappings"])
        self.assertIn("市场总龙节点纪律 -> 分歧日、首阴日、龙回头支撑日只用于市场总龙；补涨龙、支线龙、龙二龙三不做这些节点", context["field_mappings"])
        self.assertIn("周五风险 -> 周四或周五加速、周五高位博弈和周末消息不确定时，先降仓位和预期，周一再确认", context["field_mappings"])
        self.assertIn("异动监管验证 -> 监管提示后能不大跌并继续走强，才算龙头韧性；低于预期则降级", context["field_mappings"])
        self.assertIn("低开-5%处理 -> 龙头任何时候到-5%都极度小心，当天不开新仓，拉高先处理，真想参与等隔天走强", context["field_mappings"])
        self.assertIn("龙头急跌后急拉 -> 急跌后可等下一分钟急拉修复；若再转弱跌破-3%且无近端支撑，先降风险", context["field_mappings"])
        self.assertIn("加速风险 -> +7%以上或冲板按加速观察，周四周五加速更偏兑现风险，温和放量上涨更健康", context["field_mappings"])
        self.assertIn("核买核卖博弈 -> 核买后马上核卖或反向急拉急跌时，比较回撤和反击比例，空方吃掉三分之二要小心", context["field_mappings"])
        self.assertIn("龙头恐惧处理 -> 恐惧来自畏高和大亏；用低仓位试错、确认后加仓和利润壁垒替代空想勇敢", context["field_mappings"])
        self.assertIn("龙头心态纪律 -> 利润放大贪婪时继续跟随市场；看不懂就离场，不因利润垫硬格局，接受龙头结束时亏一笔", context["field_mappings"])
        self.assertIn("中军持续性 -> 板块上涨后中军次日继续放量上涨或横住，才说明大资金仍在；缩量下跌时板块延续降级", context["field_mappings"])
        self.assertIn("名字辨识度 -> 股票名称能承接题材记忆只算热度加分，必须叠加板块路径、中军和个股承接", context["field_mappings"])
        self.assertIn("板块高标反馈 -> 小弟和高标不能大面积负反馈；一字板高标跳水伤板块，板块强而龙头弱也要降级", context["field_mappings"])
        self.assertIn("抱团环境 -> 普跌环境更容易抱团市场总龙，普涨环境会降低龙头辨识度和单票溢价", context["field_mappings"])
        self.assertIn("上影线趋势警惕 -> 连续上影线说明做多被压制，次日破MA5先离场观察", context["field_mappings"])
        self.assertIn("经验规则校准 -> 避坑规则必须带重新参与条件，否则避坑会变成错过", context["field_mappings"])
        self.assertIn("启动板 -> 短线触发转趋势观察仓，必须记录启动逻辑、持股规则、破坏退出", context["field_mappings"])
        self.assertIn("趋势持股短板 -> 卖出原因可复盘，区分风险信号和情绪信号", context["field_mappings"])
        self.assertIn("盈亏同审 -> 已卖样本和持仓样本按同一套卖出原因、持股理由、失效条件、3/5/10日验证复盘", context["field_mappings"])
        self.assertIn("利润奔跑与亏损边界 -> 有趋势资格的盈利仓不因小波动提前卖，失效仓不因亏损扩大继续死拿", context["field_mappings"])
        self.assertIn("换仓错题 -> 先证明旧仓失效，再证明新仓更强，最后证明新仓风险能承受", context["field_mappings"])
        self.assertIn("亏损后切换 -> 当天默认暂停新方向，禁止用更高波动标的找回本金", context["field_mappings"])
        self.assertIn("充值补亏陷阱 -> 亏损失效仓不能靠充值加仓摊低成本，充值只能用于下一笔独立机会", context["field_mappings"])
        self.assertIn("明日交易计划 -> 账户状态、持仓处理、时间窗口、大盘剧本、板块锚点、候选预演、禁止清单", context["field_mappings"])
        self.assertIn("无计划新方向 -> 未写入前一晚计划且未通过四重确认，盘中默认没有满仓买入资格", context["field_mappings"])
        self.assertIn("日报前置风险快照 -> 日报生成先对持仓、候选、明日主买和补位全量查询公告/互动问答/投资者关系风险，盘中问股只做刷新补查", context["field_mappings"])
        self.assertIn("问答风险源配置 -> Tushare irm_qa_sh/irm_qa_sz优先，默认近10日窗口，INVESTOR_QA_ENDPOINT_URL兜底，候选比较前合并到stock_risk_map", context["field_mappings"])
        self.assertIn("盘中问股前置条件 -> 先查公告/互动问答/投资者关系风险，再看主线/承接，最后才用MA/VWAP定执行", context["field_mappings"])
        self.assertIn("盘中点位依据 -> 每个买卖点必须说明均线角色、VWAP、开盘价、前高前低、成交密集区或形态脚本", context["field_mappings"])
        self.assertIn("公告风险处理 -> 减持、强制执行、司法冻结、质押风险会让均线支撑降级为观察位", context["field_mappings"])
        self.assertIn("炒作预期降维 -> 问董秘/互动易澄清命中当前上涨发动机时加重扣分，未命中当前主线/候选理由/概念标签时只提示；强核心观察，非核心或弱势不进极度看好", context["field_mappings"])
        self.assertIn("当前上涨发动机自动推导 -> 从市场主线、候选理由、概念标签、选股宝关联板块和热门原因提取current_driver_tags，再判断澄清是否命中", context["field_mappings"])
        self.assertIn("候选质量条件链 -> 先看市场和板块，再看角色、风险、恢复条件和动作上限；条件链决定最多能做什么", context["field_mappings"])
        self.assertIn("今日总决策面板 -> 市场情绪、账户后台任务负担、今日新增上限、持仓优先动作、主买对象、补位对象、禁止动作和忽略清单先于单票排序", context["field_mappings"])
        self.assertNotIn("候选质量评分 -> 先挣分、再扣分、再动作上限；分数服务排序，动作上限决定最多能做什么", context["field_mappings"])
        self.assertIn("候选主表 -> 当前持仓、可卖数量、不可卖数量、仓位性质、账户状态、计划仓位档、实际仓位、仓位偏离、周期身份、选股质量、买点质量、风险项、成本项、动作上限、持仓动作、新开仓动作、恢复条件、取关条件、最晚复核", context["field_mappings"])
        self.assertIn("账户状态 -> 实际可买/实际不可买；只决定账户是否参与，不改变市场核心、池内身份或周期身份", context["field_mappings"])
        self.assertIn("仓位表达 -> 计划仓位档记录0/50/100策略意图，实际仓位记录一手颗粒度后的账户落点，仓位偏离说明低配或超配", context["field_mappings"])
        self.assertIn("半仓颗粒度 -> 一手实际占用40%-60%仍按50%档，不升满仓也不降观察；决策看档位，账户看实际", context["field_mappings"])
        self.assertIn("选股买点拆分 -> 好票高成本保护选股资格但不追高；差票低成本的MA/VWAP只作已有仓处理参考", context["field_mappings"])
        self.assertIn("后台任务负担 -> 未处理风险仓会占用注意力，先处理持仓风险再看新增机会，高负担时不新增参与", context["field_mappings"])
        self.assertIn("动作五层 -> 主买、补位、核心观察、修复观察、不参与；持仓动作和新开仓动作分开输出", context["field_mappings"])
        self.assertIn("盘中问股继承 -> 先读前一晚动作层级和今日新增上限；不参与不能直升主买或补位，观察类恢复条件命中也只进入复盘和下一份日报判断", context["field_mappings"])
        self.assertIn("复盘校准 -> 记录当时判断、实际走势、买点出现、用户偏离、错误归因和样本保护结果；不因单个收益结果自动调权重", context["field_mappings"])
        self.assertIn("误判归因顺序 -> 先分随机结果、决策层缺陷、AI摩擦；价格强弱和账户约束读错归决策层，话术太绝归AI摩擦，不因单次涨跌改规则", context["field_mappings"])
        self.assertIn("容量强度锚 -> 高成交高热度板块核心保留为强弱参照；账户占用过高可不参与，但不能从最终观察视野消失", context["field_mappings"])
        self.assertIn("样本保护 -> 规则变更必须同时检查核心机会、差票低成本和好票高成本样本，不能为修边角破坏大机会", context["field_mappings"])
        self.assertIn("恢复取关复核 -> 每个观察样本必须写恢复条件、取关条件和最晚复核时间，避免观察变成后台任务", context["field_mappings"])
        self.assertIn("禁止清单 -> 不该做什么优先级高于想买什么，先拦错再谈进攻", context["field_mappings"])
        self.assertIn("来源保真 -> 区分原文可支持、系统化抽象、不能归因给原文", context["field_mappings"])
        self.assertIn("新股周期 -> 市场周期、新股扩散、首日情绪、C阶段承接、情绪出口地位", context["field_mappings"])
        self.assertIn("新股样本 -> 盟固利是弱市投机宣泄；无线传媒是强修复情绪出口；历史相似不能替代当前承接验证", context["field_mappings"])
        self.assertIn("新股年景推演 -> 2015-2025未见连续两年小年；小年后先按大年假设观察，仍要用月度连续性、扩散和标志性样本验证", context["field_mappings"])
        self.assertIn("2026新股基线 -> 2025小年后按大年假设；2026-04-13启动后先按年底前持续活跃观察，但日历推演不能替代单票承接", context["field_mappings"])
        self.assertIn("风格切换 -> 主升后震荡分歧先看轮动、回流、题材活跃和连板晋级率", context["field_mappings"])
        self.assertIn("赛道题材 -> 赛道看产业持续性，题材看概念催化，二者没有好坏但执行节奏不同", context["field_mappings"])
        self.assertIn("板块叙事迁移 -> 表层行业标签要服从当日资金叙事，汽车零部件/电机在机器人语境下按人形机器人辅助判断", context["field_mappings"])
        self.assertIn("龙头回头复核 -> 低位反馈不能替代龙头顶住压力；龙头二次确认和低位/中位反馈同时出现，才记录为市场继续投票", context["field_mappings"])
        self.assertIn("科技震荡 -> 总体调整中只做聚焦参与，快进快出，低于预期先处理", context["field_mappings"])
        self.assertIn("科技支线容量条件 -> 容量参考线随当前成交额分布校准，还要看科技成交、扩散和核心承接", context["field_mappings"])
        self.assertIn("注意力发酵节点 -> 产业逻辑被集中讨论且走势仍在初期，才按支线波段观察", context["field_mappings"])
        self.assertIn("紧缺叙事 -> 支线催化优先看主线环节供需紧张，但不能替代价格承接", context["field_mappings"])
        self.assertIn("市场结构判断 -> 指数与真实赚钱效应、成交扩散、轮动性质、老主线疲态和题材新鲜度共同决定明日节奏", context["field_mappings"])
        self.assertIn("低频聚焦 -> 指数强但上涨家数弱、成交集中、对立方向反弹或老主线疲态时，只保留主线核心，不从旧方向强行扩散候选", context["field_mappings"])
        self.assertIn("稳定知识写入 LLM Wiki", context["write_boundaries"])
        self.assertIn("外部资料 -> 先来源保真归档，再沉淀知识节点", context["write_boundaries"])
        self.assertIn("知识节点 -> 写清适用场景、不适用场景、来源与证据、反证或待核实", context["write_boundaries"])
        self.assertIn("本地检索/RAG -> 只负责找材料，不替代节点判断", context["write_boundaries"])
        self.assertIn("原文不直接进入日报主链", context["report_boundaries"])
        self.assertIn("MACD只能作为辅助", context["report_boundaries"])
        self.assertIn("用户可见输出不用旧工程口径，改用资格/条件/可做/参与/不参与", context["report_boundaries"])
        self.assertIn("fresh daily generation uses Tushare-first", context["data_source_policy"])
        self.assertIn("akshare/iwencai are fallback only", context["data_source_policy"])
        self.assertIn("daily report runtime writes reports, report companion docs, snapshots, and PostgreSQL facts only", context["publish_policy"])
        self.assertIn("retired frontend/static publish paths are not part of report generation", context["publish_policy"])

    def test_context_keeps_target_dates_and_stable_manifest_without_breaking_legacy_fields(self):
        first = build_llm_wiki_context(target_date="2026-07-16", query_date="2026-07-17")
        second = build_llm_wiki_context(target_date="2026-07-16", query_date="2026-07-17")

        self.assertEqual(first["target_date"], "2026-07-16")
        self.assertEqual(first["query_date"], "2026-07-17")
        self.assertEqual(first["manifest_hash"], second["manifest_hash"])
        self.assertEqual(
            first["available_source_paths"],
            first["manifest"]["available_source_paths"],
        )
        self.assertEqual(first["source_paths"], second["source_paths"])
        self.assertEqual(first["field_mappings"], second["field_mappings"])
        self.assertEqual(
            first["confidence"],
            llm_wiki_confidence_for_availability(first["availability"]),
        )
        self.assertEqual(first["expected_source_paths"], list(dict.fromkeys(first["expected_source_paths"])))
        self.assertEqual(
            set(first["expected_source_paths"]),
            set(first["source_paths"]) | set(first["missing_source_paths"]),
        )

    def test_field_mappings_remain_compatibility_context_not_manifest_entries(self):
        compatibility_only = "只属于兼容上下文的流程说明，不是可路由知识"
        with patch(
            "knowledge.llm_wiki_context.FIELD_MAPPINGS",
            [compatibility_only],
        ):
            context = build_llm_wiki_context(
                target_date="2026-07-16",
                query_date="2026-07-17",
            )

        self.assertEqual(context["field_mappings"], [compatibility_only])
        self.assertNotIn(
            compatibility_only,
            {
                value
                for entry in context["manifest"]["entries"]
                for value in [
                    entry["knowledge_id"],
                    entry["title"],
                    *entry["trigger_terms"],
                ]
            },
        )

    def test_context_rejects_injected_manifest_with_inconsistent_availability(self):
        manifest = dict(build_llm_wiki_context()["manifest"])
        manifest["availability"] = "ready"
        manifest["manifest_hash"] = stable_json_hash(
            manifest,
            excluded_keys={"manifest_hash"},
        )

        context = build_llm_wiki_context(manifest=manifest)

        self.assertEqual(context["availability"], "invalid")
        self.assertIn("manifest_availability_inconsistent", context["warnings"])

    def test_context_reports_malformed_manifest_list_fields_without_raising(self):
        base_manifest = build_llm_wiki_context()["manifest"]
        for field in (
            "entries",
            "sources",
            "expected_source_paths",
            "available_source_paths",
            "missing_source_paths",
            "invalid_source_paths",
            "warnings",
            "errors",
        ):
            with self.subTest(field=field):
                manifest = copy.deepcopy(base_manifest)
                manifest[field] = 1
                manifest["manifest_hash"] = stable_json_hash(
                    manifest,
                    excluded_keys={"manifest_hash"},
                )

                context = build_llm_wiki_context(manifest=manifest)

                self.assertEqual(context["availability"], "invalid")
                self.assertEqual(context["confidence"], 0.0)
                self.assertIn(
                    f"manifest_field_type_invalid:{field}",
                    context["warnings"],
                )
                self.assertIsInstance(context["warnings"], list)

    def test_replay_rejects_incomplete_self_hashed_trace(self):
        trace = {
            "schema_version": "knowledge_trace.v1",
            "target_date": "2026-07-16",
            "manifest_hash": "f" * 64,
        }
        trace["trace_hash"] = stable_json_hash(trace)

        context = build_replay_llm_wiki_context(
            {
                "manifest_hash": trace["manifest_hash"],
                "knowledge_trace": trace,
            },
            target_date="2026-07-16",
            query_date="2026-07-17",
        )

        self.assertEqual(context["replay_knowledge_status"], "missing")
        self.assertEqual(context["knowledge_hits"], [])
        self.assertIn("冻结知识引用不完整", context["warnings"][0])

    def test_missing_replay_trace_defaults_query_date_to_shanghai_calendar(self):
        with patch("knowledge.llm_wiki_context.datetime") as datetime_mock:
            datetime_mock.now.return_value.date.return_value.isoformat.return_value = "2026-07-18"
            context = build_replay_llm_wiki_context(
                {},
                target_date="2026-07-16",
            )

        datetime_mock.now.assert_called_once()
        self.assertEqual(context["query_date"], "2026-07-18")
        self.assertEqual(context["knowledge_trace"]["query_date"], "2026-07-18")

    def test_fresh_trace_completeness_check_rejects_partial_context(self):
        complete = _frozen_context()
        partial = copy.deepcopy(complete)
        partial["knowledge_trace"].pop("facts_hash")
        partial["knowledge_trace"]["trace_hash"] = stable_json_hash(
            partial["knowledge_trace"],
            excluded_keys={"trace_hash"},
        )

        self.assertTrue(
            is_complete_frozen_llm_wiki_context(
                complete,
                target_date="2026-07-16",
            )
        )
        self.assertFalse(
            is_complete_frozen_llm_wiki_context(
                partial,
                target_date="2026-07-16",
            )
        )

        missing_fact_sources = copy.deepcopy(complete)
        missing_fact_sources["knowledge_trace"].pop("fact_sources")
        missing_fact_sources["knowledge_trace"]["trace_hash"] = stable_json_hash(
            missing_fact_sources["knowledge_trace"],
            excluded_keys={"trace_hash"},
        )
        self.assertFalse(
            is_complete_frozen_llm_wiki_context(
                missing_fact_sources,
                target_date="2026-07-16",
            )
        )

        forged_fact_source = copy.deepcopy(complete)
        first_path = next(iter(forged_fact_source["knowledge_trace"]["fact_sources"]))
        forged_fact_source["knowledge_trace"]["fact_sources"][first_path] = {
            "source": "official",
            "input_path": "forged://not-a-source",
        }
        forged_fact_source["knowledge_trace"]["trace_hash"] = stable_json_hash(
            forged_fact_source["knowledge_trace"],
            excluded_keys={"trace_hash"},
        )
        self.assertFalse(
            is_complete_frozen_llm_wiki_context(
                forged_fact_source,
                target_date="2026-07-16",
            )
        )

        missing_hit_sources = copy.deepcopy(complete)
        missing_hit_sources["knowledge_trace"]["hits"][0].pop(
            "matched_fact_sources"
        )
        missing_hit_sources["knowledge_trace"]["trace_hash"] = stable_json_hash(
            missing_hit_sources["knowledge_trace"],
            excluded_keys={"trace_hash"},
        )
        self.assertFalse(
            is_complete_frozen_llm_wiki_context(
                missing_hit_sources,
                target_date="2026-07-16",
            )
        )

        for field in ("decision_scope", "not_used_for"):
            with self.subTest(trace_boundary_field=field):
                missing_boundary = copy.deepcopy(complete)
                missing_boundary["knowledge_trace"].pop(field)
                missing_boundary["knowledge_trace"]["trace_hash"] = stable_json_hash(
                    missing_boundary["knowledge_trace"],
                    excluded_keys={"trace_hash"},
                )
                self.assertFalse(
                    is_complete_frozen_llm_wiki_context(
                        missing_boundary,
                        target_date="2026-07-16",
                    )
                )

    def test_frozen_trace_completeness_rejects_noncanonical_dates_even_with_valid_hash(self):
        invalid_dates = (
            "",
            " ",
            " 2026-07-16",
            "2026-07-16 ",
            "2026-7-16",
            "2026-02-30",
        )
        for invalid_date in invalid_dates:
            with self.subTest(date_field="target_date", value=repr(invalid_date)):
                frozen = _frozen_context()
                frozen["target_date"] = invalid_date
                frozen["knowledge_trace"]["target_date"] = invalid_date
                frozen["knowledge_trace"]["trace_hash"] = stable_json_hash(
                    frozen["knowledge_trace"],
                    excluded_keys={"trace_hash"},
                )

                self.assertFalse(
                    is_complete_frozen_llm_wiki_context(
                        frozen,
                        target_date=invalid_date,
                    )
                )
                replay = build_replay_llm_wiki_context(
                    frozen,
                    target_date=invalid_date,
                    query_date="2026-07-17",
                )
                self.assertEqual(replay["artifact_origin"], "missing")
                self.assertEqual(replay["knowledge_hits"], [])

        for invalid_date in invalid_dates:
            with self.subTest(date_field="query_date", value=repr(invalid_date)):
                frozen = _frozen_context()
                frozen["query_date"] = invalid_date
                frozen["knowledge_trace"]["query_date"] = invalid_date
                frozen["knowledge_trace"]["trace_hash"] = stable_json_hash(
                    frozen["knowledge_trace"],
                    excluded_keys={"trace_hash"},
                )

                self.assertFalse(
                    is_complete_frozen_llm_wiki_context(
                        frozen,
                        target_date="2026-07-16",
                    )
                )
                replay = build_replay_llm_wiki_context(
                    frozen,
                    target_date="2026-07-16",
                    query_date="2026-07-18",
                )
                self.assertEqual(replay["artifact_origin"], "missing")
                self.assertEqual(replay["knowledge_hits"], [])

    def test_frozen_trace_completeness_rejects_context_trace_query_date_mismatch(self):
        frozen = _frozen_context()
        frozen["query_date"] = "2026-07-18"

        self.assertFalse(
            is_complete_frozen_llm_wiki_context(
                frozen,
                target_date="2026-07-16",
            )
        )

    def test_fresh_trace_normalizes_list_fact_sources_and_remains_replay_safe(self):
        target_date = "2026-07-16"
        context = build_llm_wiki_context(
            target_date=target_date,
            query_date="2026-07-17",
        )
        trace = route_llm_wiki_knowledge_trace(
            {"market": {"rebound_roles": ["主动带动反弹"]}},
            manifest=context["manifest"],
            target_date=target_date,
            query_date="2026-07-17",
            facts_source="explicit",
            limit=10,
        )
        context["knowledge_trace"] = trace
        context["knowledge_hits"] = list(trace["hits"])

        self.assertEqual(
            trace["fact_sources"],
            {
                "market.rebound_roles": {
                    "source": "explicit",
                    "input_path": "knowledge_hit_facts.market.rebound_roles",
                }
            },
        )
        rebound_hit = next(
            hit
            for hit in trace["hits"]
            if hit["knowledge_id"] == "market.rebound-quality-active-passive"
        )
        self.assertEqual(rebound_hit["matched_fact_paths"], ["market.rebound_roles"])
        self.assertEqual(
            rebound_hit["matched_fact_sources"],
            [
                {
                    "path": "market.rebound_roles",
                    "source": "explicit",
                    "input_path": "knowledge_hit_facts.market.rebound_roles",
                }
            ],
        )
        self.assertTrue(
            is_complete_frozen_llm_wiki_context(
                context,
                target_date=target_date,
            )
        )

    def test_replay_rejects_frozen_hit_whose_source_differs_from_manifest(self):
        frozen = _frozen_context()
        frozen["knowledge_trace"]["hits"][0]["source_ref"]["content_hash"] = "0" * 64
        frozen["knowledge_trace"]["trace_hash"] = stable_json_hash(
            frozen["knowledge_trace"],
            excluded_keys={"trace_hash"},
        )

        context = build_replay_llm_wiki_context(
            frozen,
            target_date="2026-07-16",
            query_date="2026-07-17",
        )

        self.assertEqual(context["artifact_origin"], "missing")
        self.assertEqual(context["knowledge_hits"], [])
        self.assertIn("冻结知识引用不完整", context["warnings"][0])
        self.assertEqual(context["confidence"], 0.0)
        self.assertEqual(context["review_confidence"], 0.0)

    def test_replay_rejects_unknown_trace_availability(self):
        frozen = _frozen_context()
        frozen["knowledge_trace"]["availability"] = "unknown"
        frozen["knowledge_trace"]["trace_hash"] = stable_json_hash(
            frozen["knowledge_trace"],
            excluded_keys={"trace_hash"},
        )

        context = build_replay_llm_wiki_context(
            frozen,
            target_date="2026-07-16",
            query_date="2026-07-17",
        )

        self.assertEqual(context["artifact_origin"], "missing")
        self.assertEqual(context["knowledge_hits"], [])

    def test_replay_rejects_duplicate_frozen_trace_hits_and_ranks(self):
        frozen = _frozen_context()
        frozen["knowledge_trace"]["hits"].append(dict(frozen["knowledge_trace"]["hits"][0]))
        frozen["knowledge_trace"]["trace_hash"] = stable_json_hash(
            frozen["knowledge_trace"],
            excluded_keys={"trace_hash"},
        )

        context = build_replay_llm_wiki_context(
            frozen,
            target_date="2026-07-16",
            query_date="2026-07-17",
        )

        self.assertEqual(context["artifact_origin"], "missing")
        self.assertEqual(context["knowledge_hits"], [])
        self.assertIn("冻结知识引用不完整", context["warnings"][0])

    def test_replay_rejects_frozen_trace_from_another_target_date(self):
        context = build_replay_llm_wiki_context(
            _frozen_context("2026-07-15"),
            target_date="2026-07-16",
            query_date="2026-07-17",
        )

        self.assertEqual(context["artifact_origin"], "missing")
        self.assertEqual(context["knowledge_hits"], [])
        self.assertIn("冻结知识引用日期与目标交易日不一致", context["warnings"][0])

    def test_replay_keeps_frozen_trace_and_reports_current_source_change(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path = "wiki/交易思想/测试节点.md"
            source = root / source_path
            source.parent.mkdir(parents=True)
            source.write_text("# 测试节点\n\n第一版。\n", encoding="utf-8")
            entry = copy.deepcopy(KNOWLEDGE_INDEX[0])
            entry["source_path"] = source_path
            manifest = build_knowledge_manifest([entry], root=root, wiki_version="v1")
            frozen = build_llm_wiki_context(
                target_date="2026-07-16",
                query_date="2026-07-16",
                manifest=manifest,
                source_root=root,
            )
            trace = route_llm_wiki_knowledge_trace(
                {
                    "market": {
                        "index_trend": "上涨",
                        "breadth": "上涨家数偏弱",
                    }
                },
                manifest=manifest,
                source_root=root,
                target_date="2026-07-16",
                query_date="2026-07-16",
            )
            frozen["knowledge_trace"] = trace
            frozen["knowledge_hits"] = copy.deepcopy(trace["hits"])
            frozen_trace_hash = trace["trace_hash"]
            frozen_trace = copy.deepcopy(trace)
            frozen_manifest = copy.deepcopy(manifest)
            frozen_availability = frozen["availability"]
            source.write_text("# 测试节点\n\n第二版。\n", encoding="utf-8")

            replay = build_replay_llm_wiki_context(
                frozen,
                target_date="2026-07-16",
                query_date="2026-07-17",
                source_root=root,
            )
            replay_again = build_replay_llm_wiki_context(
                replay,
                target_date="2026-07-16",
                query_date="2026-07-18",
                source_root=root,
            )

        self.assertEqual(replay["artifact_origin"], "frozen_trace")
        self.assertEqual(replay["knowledge_trace"]["trace_hash"], frozen_trace_hash)
        self.assertEqual(replay["knowledge_trace"], frozen_trace)
        self.assertEqual(replay["manifest"], frozen_manifest)
        self.assertEqual(replay["knowledge_hits"], frozen_trace["hits"])
        self.assertEqual(replay["frozen_availability"], frozen_availability)
        self.assertEqual(replay["availability"], "source_changed")
        self.assertEqual(replay["frozen_confidence"], frozen["confidence"])
        self.assertEqual(replay["confidence"], 0.4)
        self.assertEqual(replay["review_confidence"], 0.4)
        self.assertEqual(replay["replay_source_diagnostics"]["status"], "changed")
        self.assertEqual(
            replay["replay_source_diagnostics"]["review_availability"],
            "source_changed",
        )
        self.assertIn(
            f"source_content_hash_mismatch:{source_path}",
            replay["replay_source_diagnostics"]["issues"],
        )
        self.assertTrue(
            any("当前经验库来源与冻结版本不同" in item for item in replay["warnings"])
        )
        self.assertEqual(replay_again["artifact_origin"], "frozen_trace")
        self.assertEqual(replay_again["manifest"], frozen_manifest)
        self.assertEqual(replay_again["knowledge_trace"], frozen_trace)
        self.assertEqual(replay_again["knowledge_hits"], frozen_trace["hits"])
        self.assertEqual(replay_again["availability"], "source_changed")
        self.assertEqual(replay_again["frozen_confidence"], frozen["confidence"])
        self.assertEqual(replay_again["confidence"], 0.4)
        self.assertEqual(replay_again["review_confidence"], 0.4)

    def test_build_llm_wiki_context_exposes_selection_shape_ascii_flow(self):
        context = build_llm_wiki_context()

        self.assertIn("process_flows", context)
        flow_text = "\n".join(context["process_flows"])
        for required in [
            "选股形态审美 ASCII 流程图",
            "fetch_recent_price_bars",
            "lookback_days=120",
            "recent_bars",
            "recent_extreme_conviction_mentions",
            "明日极度看好近25日跟踪表",
            "过程观察25日跟踪表",
            "重点观察历史回测表",
            "观察位窗口",
            "观察位质量",
            "_build_trend_aesthetic_review",
            "selection_shape_review",
            "shape_repair_pool",
            "dragon_rebound_watch_pool",
            "final_risk_review",
            "common_selection_check",
            "明日极度看好比较",
            "形态待修复池",
            "龙回头观察池",
            "继续走坏取关淘汰",
            "0%不参与",
            "候选观察",
            "上证缠论",
            "明日执行计划",
            "明日抉择",
            "不作为明日新增参与依据",
            "+-->",
        ]:
            self.assertIn(required, flow_text)

    def test_build_llm_wiki_context_exposes_vehicle_mismatch_and_new_theme_timing(self):
        context = build_llm_wiki_context()
        digest = context["report_digest_text"]
        wiki_text = (ROOT / "wiki/板块补充/板块中枢与主线延续.md").read_text(encoding="utf-8")

        self.assertIn(
            "资金载体错配 -> 叙事、核心锚、弹性载体和参与资金不在同一周期时，不能用统一持股剧本",
            context["field_mappings"],
        )
        self.assertIn(
            "新题材早信/不信 -> 真新题材只在早期主动性和第一执行窗口提高参与质量，后手只观察或等分歧条件",
            context["field_mappings"],
        )
        self.assertIn("板块反弹质量与主动被动分层", wiki_text)
        self.assertIn("板块指数先判生死", wiki_text)
        self.assertIn("主动做多优先级更高", wiki_text)
        self.assertIn("主动带动反弹", wiki_text)
        self.assertIn("跟随指数反弹", wiki_text)
        self.assertIn("熟悉资产修复", wiki_text)
        self.assertIn("节奏共振待确认", wiki_text)
        self.assertIn("持仓分类落地", wiki_text)
        self.assertIn(
            "板块反弹质量 -> 板块指数走坏时反弹先按卖点或减风险；板块指数仍好且窗口、承接和亏损边界清楚时才提高参与质量",
            context["field_mappings"],
        )
        self.assertIn(
            "主动被动分层 -> 盘中被资金主动做多后被指数下跌带回的板块，次日指数修复时优先观察重新进攻；主动冲高回落则按走坏处理",
            context["field_mappings"],
        )
        self.assertIn(
            "冰点接冰点与值博率 -> 连续预期反弹却继续跌不能否认，但连续压缩会改变值博率；提前写清反弹来时做什么",
            context["field_mappings"],
        )
        self.assertIn(
            "反弹三分类 -> 主动带动反弹看参与，跟随指数反弹看减风险，熟悉资产修复看持续承接；板块高潮碰上指数深V时先写共振待确认",
            context["field_mappings"],
        )
        self.assertIn("载体错配先判周期", digest)

    def test_sector_grid_first_selection_enters_llm_wiki(self):
        context = build_llm_wiki_context()
        wiki_text = (ROOT / "wiki/板块补充/板块中枢与主线延续.md").read_text(encoding="utf-8")
        digest = context["report_digest_text"]

        self.assertIn("### 水池九宫格与先选板块", wiki_text)
        self.assertIn("统一翻译成 `先选板块`", wiki_text)
        self.assertIn("边角标的不在资金优先灌入区", wiki_text)
        self.assertIn(
            "水池九宫格 -> 全市场资金水池被板块网格化，结构性行情先看资金灌入哪个板块格子，再看个股属于主线、短线还是边角",
            context["field_mappings"],
        )
        self.assertIn(
            "先选板块 -> 指数强不等于普涨；先判被资金选择的板块路径和资金柱高度，再评估个股角色、承接、价格和账户",
            context["field_mappings"],
        )
        self.assertIn(
            "边角标的 -> 没站在被资金选择的格子里时，不因轮动自动取得参与资格；先承认位置不占优，再决定是否继续观察",
            context["field_mappings"],
        )
        self.assertIn("水池九宫格先选板块", digest)

    def test_build_llm_wiki_context_exposes_knowledge_compounding_candidates(self):
        context = build_llm_wiki_context()

        candidates = context.get("knowledge_compounding_candidates")
        self.assertIsInstance(candidates, list)
        self.assertEqual(len(candidates), 2)

        candidate = candidates[0]
        self.assertEqual(
            candidate.get("related_nodes"),
            ["AI摩擦与知识复利", "判断样本与市场演变"],
        )
        self.assertEqual(candidate.get("status"), "待确认")
        self.assertEqual(
            candidate.get("new_insight"),
            "判断样本是日报里的反馈机制，用来把 AI 省掉的认知摩擦补回来。",
        )
        self.assertIn("只进入知识复利候选", candidate.get("action", ""))
        self.assertIn("不自动写入正式 wiki", candidate.get("action", ""))
        self.assertIn("不改变交易动作", candidate.get("action", ""))

        second = candidates[1]
        self.assertEqual(
            second.get("related_nodes"),
            ["价格行为与能量框架", "判断样本与市场演变"],
        )
        self.assertEqual(second.get("status"), "已入库")
        self.assertEqual(
            second.get("new_insight"),
            "反弹回落后不再创新低、底部慢慢抬高，才有短线波段关注意义。",
        )
        self.assertIn("已写入价格行为节点", second.get("action", ""))
        self.assertIn("可跟踪波段", second.get("action", ""))

    def test_build_llm_wiki_context_records_external_insight_fieldization(self):
        context = build_llm_wiki_context()
        wiki_text = (ROOT / "wiki/交易思想/AI摩擦与知识复利.md").read_text(encoding="utf-8")
        digest = context["report_digest_text"]

        self.assertIn(
            "外部启发转交易规则 -> 先分原文可支持、系统化抽象、不能归因给原文，再落到市场条件、参与边界和复盘反证",
            context["field_mappings"],
        )
        self.assertIn(
            "自以为是校准 -> 判断欲强时先回到价格事实、账户占用、亏损边界和失效条件，不用顺口类比替代可复盘字段",
            context["field_mappings"],
        )
        self.assertIn("外部启发转交易规则", wiki_text)
        self.assertIn("顺口类比", wiki_text)
        self.assertIn("市场条件、参与边界和复盘反证", wiki_text)
        self.assertIn("外部启发先做来源保真再落字段", digest)
        self.assertIn("判断欲强先回价格账户亏损边界失效条件", digest)

    def test_llm_wiki_maintenance_contract_enters_compact_context(self):
        context = build_llm_wiki_context()
        wiki_text = (ROOT / "wiki/运行契约/LLM Wiki维护与路由契约.md").read_text(encoding="utf-8")

        for required in [
            "来源保真",
            "路由提示",
            "回答反哺规则",
        ]:
            self.assertIn(required, wiki_text)

        for required in [
            "外部资料 -> 先来源保真归档，再沉淀知识节点",
            "知识节点 -> 写清适用场景、不适用场景、来源与证据、反证或待核实",
            "本地检索/RAG -> 只负责找材料，不替代节点判断",
        ]:
            self.assertIn(required, context["write_boundaries"])

    def test_price_action_wiki_records_present_execution_rule(self):
        context = build_llm_wiki_context()
        wiki_text = (ROOT / "wiki/交易思想/价格行为与能量框架.md").read_text(encoding="utf-8")
        field_mappings = context["field_mappings"]
        digest = context["report_digest_text"]

        for required in [
            "当下执行与心理时间校准",
            "Roger 的《当下的力量》读书笔记",
            "心理时间",
            "当下事情可以应付，未来只存在于思维里",
            "钟表时间可以用于复盘、计划、目标和预测",
            "短线的本质是当下",
            "未来想象只能写进观察或研究，不直接给买入资格",
            "遥不可及的价值投资叙事",
            "新股上市当天暴涨想象",
            "当下不是只看一秒钟分时",
            "现在有没有执行资格",
            "短线不期待遥不可及的长期兑现，也不赌新股上市当天的神迹",
            "当下执行",
            "心理时间校准",
            "短线当下性",
        ]:
            self.assertIn(required, wiki_text)

        for required in [
            "当下执行 -> 盘中只执行、取消或降风险昨晚日报已决定的动作；新增证据只能进入复盘和下一份日报判断",
            "心理时间校准 -> 未来大机会、长期价值兑现、新股首日暴涨和题材后续发酵，只能进入观察或研究，不能压迫当下动作",
            "短线当下性 -> 短线不期待遥不可及的兑现，也不赌神迹；计划可以面向未来，执行只能落在当前可验证事实",
        ]:
            self.assertIn(required, field_mappings)

        self.assertIn("短线当下不赌未来", digest)

    def test_llm_wiki_context_records_rhythm_reset_margin_review_without_forbidden_terms(self):
        context = build_llm_wiki_context()
        wiki_text = (ROOT / "wiki/交易思想/价格行为与能量框架.md").read_text(encoding="utf-8")
        sector_text = (ROOT / "wiki/板块补充/板块中枢与主线延续.md").read_text(encoding="utf-8")
        field_mappings = context["field_mappings"]
        daily_lines = context["daily_discipline_lines"]

        for required in [
            "公共合理与超短边际",
            "节奏复位空仓",
            "延后确认空仓",
            "错失待批改",
            "合理不是超额收益来源",
            "复核对象为什么需要批改，为什么 T0 不能做，T+1 出现什么条件才恢复执行资格",
            "必须明确它不是 T0 答案",
        ]:
            self.assertIn(required, wiki_text)
        for required in [
            "外盘上行、存储大涨或美股科技链拉升同理",
            "默认仍是噪音",
            "进入 T+1 复核",
        ]:
            self.assertIn(required, sector_text)
        for required in [
            "节奏复位空仓 -> 0%不是思考终点；旧目标尾端或步伐踏错时先停下来，再反推边际主线和次日复核路径",
            "延后确认空仓 -> T0看到可能新主线但板块扩散、A股映射、承接窗口或亏损边界不完整，只进入T+1复核",
            "错失待批改 -> 次日事实只用于批改是否过度防守或漏判，不回写T0结论，也不把过程候选写成明日执行对象",
            "公共合理不等于超短边际 -> 合理空仓可以保命，但超短还要解释有没有边际主线、旧目标尾端和确认延后",
            "旧信号源批改 -> 周一空仓且旧目标来自周五信号时，必须批改周五选股、买点、持仓预期和退出纪律；周二走强只算重新比较，不替周五或周一正名",
            "外盘主线传导复核 -> 外盘默认噪音；海外同链定价、亚洲确认、A股映射、板块扩散和核心承接完整后才进入T+1复核",
        ]:
            self.assertIn(required, field_mappings)
        self.assertIn(
            "节奏复位空仓和延后确认空仓只解释候选复核，不改变最终0%动作；T+1强弱只能进入批改和下一份日报。",
            daily_lines,
        )

        new_text = "\n".join(
            [
                item
                for item in [*field_mappings, *daily_lines]
                if "节奏复位空仓" in item
                or "延后确认空仓" in item
                or "错失待批改" in item
                or "公共合理" in item
                or "外盘主线传导" in item
            ]
        )
        for forbidden in [_m("硬", "门", "禁"), _m("门", "禁"), _m("ga", "te"), _m("状态", "机")]:
            self.assertNotIn(forbidden, new_text)

    def test_llm_wiki_context_records_performance_rotation_main_attack(self):
        context = build_llm_wiki_context()
        sector_text = (ROOT / "wiki/板块补充/板块中枢与主线延续.md").read_text(encoding="utf-8")
        price_text = (ROOT / "wiki/交易思想/价格行为与能量框架.md").read_text(encoding="utf-8")
        field_mappings = context["field_mappings"]

        for required in [
            "业绩线与战术主攻切换",
            "主线不是信仰位，而是战术资源",
            "科技线、AI硬件或海外链仍是市场重要资源",
            "业绩+板块趋势共振",
            "轮动线 > 科技国产链 > 科技海外链",
            "把超级明星作为牵制点",
        ]:
            self.assertIn(required, sector_text)
        for required in [
            "风格切换载体",
            "主线真空期",
            "主线资源不是信仰位",
        ]:
            self.assertIn(required, price_text)
        for required in [
            "主线战术资源 -> 科技线可以从主攻点降为牵制点；业绩线、轮动线和低位趋势线只要走势活跃且板块逻辑共振，就要同权比较",
            "业绩趋势共振 -> 业绩超预期不是买点；业绩、板块趋势、价格结构和资金扩散同时成立，才提高观察质量",
            "风格切换载体 -> 主线真空期的强势样本不是标准答案，但最终0%后必须复核它是孤立情绪还是带出扩散承接",
        ]:
            self.assertIn(required, field_mappings)

    def test_price_action_wiki_records_higher_low_short_swing_rule(self):
        context = build_llm_wiki_context()
        wiki_text = (ROOT / "wiki/交易思想/价格行为与能量框架.md").read_text(encoding="utf-8")
        digest = context["report_digest_text"]

        self.assertIn(
            "反弹回落后如果低点不再创新低、底部开始慢慢抬高，才有短线波段关注意义",
            wiki_text,
        )
        self.assertIn(
            "震荡市短线波段 -> 连跌后只允许轻仓低吸，反弹后不再创新低、底部抬高才有波段关注意义，不把低吸扩成满仓趋势持有",
            context["field_mappings"],
        )
        self.assertIn("底抬高看波段", digest)

    def test_ai_friction_wiki_records_copying_with_focus_and_idea(self):
        context = build_llm_wiki_context()
        wiki_text = (ROOT / "wiki/交易思想/AI摩擦与知识复利.md").read_text(encoding="utf-8")

        for required in [
            "模仿学习校准",
            "抄袭不可怕",
            "重心和理念",
            "初学至少八分像",
            "成熟后三五分取骨架",
            "初学乱发挥",
            "成熟后不思进取",
        ]:
            self.assertIn(required, wiki_text)

        self.assertIn(
            "模仿学习校准 -> 抄袭不可怕，怕的是不知道抄的重心和理念；初学先八分像拿正反馈，成熟后取三五分骨架迁移",
            context["field_mappings"],
        )

    def test_action_layer_wiki_records_position_and_inside_boundary_discipline(self):
        context = build_llm_wiki_context()
        wiki_text = (ROOT / "wiki/交易思想/扣分系统与动作分层.md").read_text(encoding="utf-8")
        digest = context["report_digest_text"]

        for required in [
            "## 位置与线内动作",
            "位置先于能力",
            "动作线头",
            "线内动作",
            "愿望事实分离",
            "边界外不证明自己",
        ]:
            self.assertIn(required, wiki_text)

        for required in [
            "位置先于能力 -> 先判市场阶段、账户状态、持仓身份和先后手，再给参与动作",
            "线内动作 -> 主线、辨识度、承接、时间窗口、失效条件和账户承受力清楚才参与；边界外不证明自己",
            "愿望事实分离 -> 应该要拉、跌多了、逻辑没问题不能替代价格承接和失效条件",
        ]:
            self.assertIn(required, context["field_mappings"])

        self.assertIn("位置先于能力", digest)
        self.assertIn("线内动作边界外不证明自己", digest)
        self.assertIn("愿望不替代承接失效条件", digest)

    def test_build_llm_wiki_context_keeps_report_digest_short_and_fieldized(self):
        context = build_llm_wiki_context()
        digest = context["report_digest_text"]

        self.assertIn("角度与幅度", digest)
        self.assertIn("价格是裁判", digest)
        self.assertIn("资金流和指标只作辅助", digest)
        self.assertIn("消息只确认风险不生成买点", digest)
        self.assertIn("板块节奏优先", digest)
        self.assertIn("MA只做执行锚点", digest)
        self.assertIn("该涨不涨降级", digest)
        self.assertIn("低回撤和稳定复利优先", digest)
        self.assertIn("日赚1%不是稳定目标", digest)
        self.assertIn("月度15%-20%非每日要求", digest)
        self.assertIn("小资金靠少数高质量核心机会", digest)
        self.assertIn("轻仓确认后加冲高分批卖破结构减", digest)
        self.assertIn("3%-5%浮亏先检查买入理由", digest)
        self.assertIn("结构破坏才处理个股-10%事故极限", digest)
        self.assertIn("账户不能被普通波动打残", digest)
        self.assertIn("攻击频次服从亏损边界", digest)
        self.assertIn("先避免大亏再追求大赚", digest)
        self.assertIn("收益风险不对称收益靠近弹性亏损边界收敛", digest)
        self.assertIn("胜率难绝对统治时靠赔率", digest)
        self.assertIn("做T先确认不贪低", digest)
        self.assertIn("T博值防守止盈", digest)
        self.assertIn("市场兜底不等于决策正确", digest)
        self.assertIn("同天样本先强度后账户买不了不降级", digest)
        self.assertIn("强票可买不用弱替代", digest)
        self.assertIn("汰弱留强新旧", digest)
        self.assertIn(
            "去弱留强是短线执行表达：卖旧仓看旧仓资格，买新仓看新仓资格；不能用FOMO把两笔判断合成一次满仓替换。",
            context["daily_discipline_lines"],
        )
        self.assertIn(
            "反包先批改情绪反应，不直接批改前一日信息集；正确动作出现亏损结果，仍按可控小亏和纪律成本复盘。",
            context["daily_discipline_lines"],
        )
        self.assertIn(
            "必卖日里，反抽、0轴、VWAP和开盘价修复先看作旧仓退出流动性；价格只决定卖得舒服还是狼狈，不重新决定卖不卖。",
            context["daily_discipline_lines"],
        )
        self.assertIn(
            "Ta-Te账户日序表必须区分历史路径、今日报告和明日执行：Ta最远，Tb/Tc是前两段，Td是报告日，Te是明日执行日；明日标的为空时，Te写只处理旧仓风险或空仓等待B1资格。",
            context["daily_discipline_lines"],
        )
        self.assertIn(
            "日报不是每天预测一个股；先判断是否有可参与节拍，没有买入资格就0%不参与；B1只买参与权，B2等待确认。",
            context["daily_discipline_lines"],
        )
        self.assertIn("震荡市连跌轻仓低吸、反弹卖回", digest)
        self.assertIn("一九行情看图优先", digest)
        self.assertIn("题材降权图形走差抓紧降风险", digest)
        self.assertIn("趋势股图形走弱越跌越减", digest)
        self.assertIn("MA组合只做执行锚点", digest)
        self.assertIn("板块节奏优先", digest)
        self.assertIn("指数强家数弱按窄池子", digest)
        self.assertIn("量化仍在看占比宽度核心承接", digest)
        self.assertIn("占比回落后排掉队核心跌回VWAP或关键均线先退出", digest)
        self.assertIn("迹象到规律再到实战运用", digest)
        self.assertIn("弱方向掉队强方向扩散承接才参与", digest)
        self.assertIn("涨停数量看情绪位置看信心", digest)
        self.assertIn("高位承接才进攻低位首板偏反弹", digest)
        self.assertIn("短线超短主战场追求500强", digest)
        self.assertIn("非主战场不拖后腿不扩战法", digest)
        self.assertIn("正确风险选高辨识度用策略压下行", digest)
        self.assertIn("上影线按身份分层", digest)
        self.assertIn("非0%且资格成立才给明日主买1只补位1只", digest)
        self.assertIn("0%无唯一对象只观察", digest)
        self.assertIn("历史表统一观察位窗口", digest)
        self.assertIn("上证缠论计划抉择同向只观察", digest)
        self.assertIn("速度档", digest)
        self.assertIn("共同选择", digest)
        self.assertIn("对子整数只作锚点", digest)
        self.assertIn("顶部冲不过先止盈", digest)
        self.assertIn("底部VWAP承接试错", digest)
        self.assertIn("反包先按兑现点", digest)
        self.assertIn("公告风险取消主买补位资格", digest)
        self.assertIn("趋势审美看120日日K", digest)
        self.assertIn("选股形态看呼吸感蛇形走位", digest)
        self.assertIn("A杀放量下杀反抽不过关键线高低点下移只观察", digest)
        self.assertIn("小资金高弹性只做热门核心", digest)
        self.assertIn("小资金优势灵活切换核心", digest)
        self.assertIn("AI筛核心拦错误做复盘", digest)
        self.assertIn("辨识度优先", digest)
        self.assertIn("短线当下不赌未来", digest)
        self.assertIn("低流动性锯齿涨停不升格", digest)
        self.assertIn("买点卖点底层操作", digest)
        self.assertIn("MA3/MA7/MA10/MA20", digest)
        self.assertIn("点位说明MA/VWAP/开盘价/前高低/密集区/形态", digest)
        self.assertIn("V/M/W/A按确认与破坏执行", digest)
        self.assertIn("烂板停顿空中加油不追", digest)
        self.assertIn("等重新承接", digest)
        self.assertIn("紧急止损规则", digest)
        self.assertIn("放量大跌超7%", digest)
        self.assertIn("成交量确认", digest)
        self.assertIn("指数价跌量增先防踩踏", digest)
        self.assertIn("局部强势只按逆势试攻", digest)
        self.assertIn("情绪总状态先看盘面亏钱效应", digest)
        self.assertIn("局部指标高潮只写局部过热", digest)
        self.assertIn("低位横盘突放量再缩量二次启动纳入强势样本", digest)
        self.assertIn("无公开题材异动只记资金表态", digest)
        self.assertIn("低开不超-3%收复0轴站稳黄线才算主动", digest)
        self.assertIn("不新增0940窗口", digest)
        self.assertIn("特殊节点隔日确认", digest)
        self.assertIn("市场总龙才做分歧首阴龙回头", digest)
        self.assertIn("周五和加速先防风险", digest)
        self.assertIn("监管后不大跌才算韧性", digest)
        self.assertIn("-5%当天不开新仓", digest)
        self.assertIn("急跌等下一分钟急拉修复", digest)
        self.assertIn("核买核卖看三分之二力量", digest)
        self.assertIn("老龙未死不做新龙", digest)
        self.assertIn("低仓试错利润壁垒克服畏高恐惧", digest)
        self.assertIn("看不懂离场不靠利润垫硬格局", digest)
        self.assertIn("接受龙头结束亏一笔", digest)
        self.assertIn("中军次日放量或横住验证板块延续", digest)
        self.assertIn("名字辨识度只作热度加分", digest)
        self.assertIn("高标小弟大面积负反馈降级", digest)
        self.assertIn("普跌抱团普涨降辨识度", digest)
        self.assertIn("连续上影破MA5先离场", digest)
        self.assertIn("避坑规则带重新参与条件", digest)
        self.assertIn("换仓先证旧仓失效、新仓更强、风险能承受", digest)
        self.assertIn("亏损仓不靠充值加仓摊低成本", digest)
        self.assertIn("前夜计划先定账户状态和禁止清单", digest)
        self.assertIn("不可买仍在池只观察不参与今日比较", digest)
        self.assertIn("计划仓位管意图实际仓位管落账", digest)
        self.assertIn("无计划新方向盘中无满仓资格", digest)
        self.assertIn("问股先查公告风险", digest)
        self.assertIn("风险源配到stock_risk_map", digest)
        self.assertIn("每个买卖点说明点位依据", digest)
        self.assertIn("减持强制执行让均线支撑降级", digest)
        self.assertIn("固定交易窗口条件", digest)
        self.assertIn("普通结构看09:50-10:10窗口", digest)
        self.assertIn("强核心开盘核心", digest)
        self.assertIn("09:50-10:10窗口", digest)
        self.assertIn("买卖窗口0930-0935/0950-1010/1430-1455", digest)
        self.assertIn("失效价和单笔-5%底线", digest)
        self.assertIn("资格条件可做参与", digest)
        self.assertLessEqual(len(digest), 1500)
        self.assertNotIn("缠论原文", digest)
        self.assertNotIn("能量学", digest)
        self.assertNotIn("教你炒股票", digest)

    def test_market_evolution_wiki_records_limit_up_position_confidence(self):
        wiki_text = (ROOT / "wiki/交易思想/判断样本与市场演变.md").read_text(encoding="utf-8")

        for required in [
            "涨停位置与资金信心",
            "高位承接反证",
            "涨停数量只说明情绪活跃",
            "涨停落点才说明资金信心",
            "低位首板、超跌首板和分散点火",
            "limit_up_position_confidence",
            "high_level_acceptance_evidence",
            "low_level_first_board_rebound",
            "先按反弹情绪处理",
        ]:
            self.assertIn(required, wiki_text)

    def test_t_risk_control_wiki_records_expected_value_rule(self):
        wiki_text = (ROOT / "wiki/交易思想/做T与风险控制.md").read_text(encoding="utf-8")

        self.assertIn("## T仓博值率", wiki_text)
        self.assertIn("下方防守和上方兑现", wiki_text)
        self.assertIn("只有防守线、没有止盈线", wiki_text)
        self.assertIn("MA3/VWAP附近只提供执行锚点", wiki_text)

    def test_same_stock_t_failure_rule_enters_wiki_context(self):
        context = build_llm_wiki_context()
        wiki_text = (ROOT / "wiki/交易思想/做T与风险控制.md").read_text(encoding="utf-8")
        mistake_text = (ROOT / "wiki/交易思想/交易错题本.md").read_text(encoding="utf-8")
        readme_text = (ROOT / "wiki/README.md").read_text(encoding="utf-8")
        field_mappings = context["field_mappings"]
        digest = context["report_digest_text"]

        for required in [
            "同股T强表态失败规则",
            "已有 `1x` 旧仓时，同一只票继续出现在今日目标里",
            "强表态存活才允许临时2x",
            "跌破 VWAP 后又跌破昨收",
            "卖出全部可卖旧仓",
            "same_stock_t_temporary_2x",
            "opening_spike_survival_required",
            "same_stock_t_failure_exit_old_position",
            "normal_tail_exit_failed_sample_split",
            "2B参与权与确认权规则",
            "B1参与权",
            "B2确认权",
            "B2不是任务仓",
            "态度不是仓位",
            "仓位是证据强度的结果",
            "bad_sample_b1_good_sample_b1_b2",
            "confirm_then_accelerate",
        ]:
            self.assertIn(required, wiki_text)

        for required in [
            "错题四：太极实业同股T把强表态当买入资格",
            "09:35 股价回落到 `30.41`",
            "尾盘卖旧仓是正确补救，但不是满分处理",
            "同股T失败后，先卖可卖旧仓",
            "把“我已经决定要买”理解成“集合竞价必须一次买够”",
            "B2不是任务仓，没有确认就没有补足义务",
            "开盘用小仓买可能性，确认后用大仓买确定性",
        ]:
            self.assertIn(required, mistake_text)

        self.assertIn("同股T、已有1x同股继续", readme_text)
        self.assertIn("临时2x、强表态失败", readme_text)
        self.assertIn("2B法、B1/B2、参与权/确认权、必须买够、怕小赚", readme_text)
        self.assertIn(
            "同股T临时2x -> 已有1x且今日目标仍是同一只票时只按同股T候选处理；强表态存活才允许临时2x，失败后卖可卖旧仓",
            field_mappings,
        )
        self.assertIn(
            "强表态失败 -> 09:30-09:35急拉只作观察；快速跌破VWAP、昨收或MA7且不能收回时，不新增并按失败样本处理",
            field_mappings,
        )
        self.assertIn(
            "尾盘卖出边界 -> 早盘买入次日尾盘卖出只适用于正常样本；失败样本接近最大亏损或跌破关键线时先处理风险",
            field_mappings,
        )
        self.assertIn(
            "2B参与确认 -> B1买参与权，B2买确认权；B2不是任务仓，没有确认就没有补足义务",
            field_mappings,
        )
        self.assertIn(
            "态度不是仓位 -> 集合竞价买一部分已经表达态度，剩余仓位必须留给市场确认",
            field_mappings,
        )

    def test_t_risk_control_wiki_records_zero_axis_impulse_rule(self):
        context = build_llm_wiki_context()
        wiki_text = (ROOT / "wiki/交易思想/做T与风险控制.md").read_text(encoding="utf-8")
        field_mappings = context["field_mappings"]
        digest = context["report_digest_text"]

        for required in [
            "0轴冲动买入错题规则",
            "10:10之后，0轴只能看，不能买",
            "做T买点必须贴近认错线",
            "随意时间点买入一律记为计划外交易",
            "这不是盘感，是破坏纪律",
            "zero_axis_no_buy_rule",
            "random_time_buy_ban",
            "ma5_touch_before_t_buy",
            "break_rule_wakeup_review",
            "把观察信号错当成买入资格",
            "把盘中冲动包装成临盘应变",
            "impulse_disguised_as_adaptation",
            "长期赚钱的人不一定天生没有冲动",
            "冲动不能直接变成交易动作",
            "只参与那些让我从容的机会",
            "calm_trader_personality_rule",
        ]:
            self.assertIn(required, wiki_text)

        self.assertIn(
            "0轴不作做T买点 -> 0轴只观察动能强弱；10:10之后尤其不能因为将要突破0轴而新增买入",
            field_mappings,
        )
        self.assertIn(
            "随意时间点买入禁止 -> 三段买卖窗口外不新增主动买入；破坏时间纪律后当天只处理风险和写错题复盘",
            field_mappings,
        )
        self.assertIn(
            "从容交易人格 -> 长期赚钱的人不是没有冲动，而是不让冲动直接变成交易动作；只参与让自己从容的机会",
            field_mappings,
        )
        self.assertIn("0轴禁买观非资冲非变", digest)

    def test_t_risk_control_wiki_records_profit_after_win_discipline(self):
        context = build_llm_wiki_context()
        wiki_text = (ROOT / "wiki/交易思想/做T与风险控制.md").read_text(encoding="utf-8")
        field_mappings = context["field_mappings"]
        digest = context["report_digest_text"]

        for required in [
            "盈利后失控与顺境收紧规则",
            "不复刻原文长文、评论区和股票名单",
            "连续盈利后放松规则",
            "赚钱后把短期手感当成永久实力",
            "无趣交易的价值",
            "判断环境不只看指数红绿",
            "连板高度、热点宽度、各线路活跃股梯队和高位异动群体",
            "连续两笔交易不符合预演、触发失效或明显低于预期，直接停手",
            "profit_after_win_tilt",
            "boring_trade_survival",
            "two_bad_trades_stop",
            "active_money_weather_vane",
            "strong_pool_deterioration_stop",
            "strong_repair_reentry_signal",
        ]:
            self.assertIn(required, wiki_text)

        for required in [
            "盈利后失控防线 -> 连续盈利后先复核仓位、窗口、失效线和禁止清单，不把短期手感当永久实力",
            "无趣交易生存 -> 条件执行、见好就收、严格失效和看不懂空仓，优先保护长期可执行性",
            "两笔异常停手 -> 连续两笔不符合预演或触发失效，直接停手观察股池，不用第三笔证明自己",
            "活跃资金风向标 -> 连板高度、热点宽度、活跃股梯队和高位异动群体爆发率共同判断环境",
            "强者修复再参与 -> 高位反包、V型修复和板块承接同步出现后，才从观察恢复参与",
        ]:
            self.assertIn(required, field_mappings)

        self.assertIn("盈停修", digest)

    def test_price_action_wiki_records_asymmetric_risk_reward_rule(self):
        wiki_text = (ROOT / "wiki/交易思想/价格行为与能量框架.md").read_text(encoding="utf-8")

        self.assertIn("收益风险不能按静态对称理解", wiki_text)
        self.assertIn("让收益尽量靠近强势弹性，让亏损边界尽量收敛", wiki_text)
        self.assertIn("收益风险不对称", wiki_text)

    def test_price_action_wiki_records_high_position_no_chase_shapes(self):
        wiki_text = (ROOT / "wiki/交易思想/价格行为与能量框架.md").read_text(encoding="utf-8")

        for required in [
            "高位后手不追形态",
            "烂板不追",
            "停顿不追",
            "空中加油不追",
            "分歧后的重新承接",
            "已有仓",
            "新仓",
            "不新增独立选股逻辑",
        ]:
            self.assertIn(required, wiki_text)

    def test_price_action_wiki_records_fake_bottom_and_attack_shape(self):
        price_action = (ROOT / "wiki/交易思想/价格行为与能量框架.md").read_text(encoding="utf-8")

        for required in [
            "图形美学：假底与进攻雏形",
            "真正的进攻雏形通常不制造立刻想买的兴奋，而是让人想再等等",
            "小K线、窄振幅、缩量横盘、收盘重心缓慢上移",
            "逐步靠近前高本身不是终点风险",
            "利空不深跌、利好不大涨",
            "阳包阴、突破阳线或明确异动",
            "票虽好，但是要再等等",
        ]:
            self.assertIn(required, price_action)

    def test_price_action_wiki_records_low_volume_sideways_and_intraday_leader_rules(self):
        wiki_text = (ROOT / "wiki/交易思想/价格行为与能量框架.md").read_text(encoding="utf-8")

        for required in [
            "低位缩量横盘与试龙头",
            "长期低位缩量横盘",
            "突放巨量",
            "涨停或炸板",
            "二次启动",
            "无公开题材异动",
            "不能直接写成已知利好",
            "龙头日内强弱脚本",
            "09:30-09:35",
            "不新增 09:40",
            "收复0轴",
            "分时黄线",
            "开盘 -5% 以下",
            "尾盘大幅下杀",
            "1分钟分时",
            "MA10/MA20",
        ]:
            self.assertIn(required, wiki_text)

    def test_price_action_wiki_records_leader_special_nodes_and_holding_discipline(self):
        wiki_text = (ROOT / "wiki/交易思想/价格行为与能量框架.md").read_text(encoding="utf-8")

        for required in [
            "龙头特殊节点与持仓纪律",
            "特殊节点隔日确认",
            "龙头分歧日",
            "首阴日",
            "龙回头支撑日",
            "市场总龙节点纪律",
            "补涨龙、支线龙、龙二龙三",
            "周五风险",
            "异动监管验证",
            "老龙未死不做新龙",
            "低开-5%处理",
            "龙头急跌后急拉",
            "加速风险",
            "核买核卖博弈",
            "龙头阴线修复",
            "龙头心态纪律",
            "龙头恐惧处理",
            "畏高和大亏",
            "低仓位试错",
            "利润壁垒",
            "看不懂就离场",
            "不因利润垫硬格局",
            "接受龙头结束时亏一笔",
            "原文可直接支持",
            "系统化抽象",
            "不能归因给原文",
        ]:
            self.assertIn(required, wiki_text)

    def test_sector_wiki_records_middle_core_continuation_and_name_recognition(self):
        wiki_text = (ROOT / "wiki/板块补充/板块中枢与主线延续.md").read_text(encoding="utf-8")

        for required in [
            "中军持续性与名字辨识度",
            "中军",
            "次日继续放量上涨",
            "横住不破",
            "缩量下跌",
            "板块延续降级",
            "名字辨识度",
            "热度加分",
            "不能替代板块路径",
            "板块高标反馈与抱团环境",
            "板块高标反馈",
            "大面积负反馈",
            "一字板高标跳水",
            "板块强而龙头弱",
            "抱团环境",
            "普跌环境",
            "普涨环境",
        ]:
            self.assertIn(required, wiki_text)

    def test_llm_wiki_records_final_target_resolution_output_contract(self):
        context = build_llm_wiki_context()
        digest = context["report_digest_text"]
        flows = "\n".join(context["process_flows"])

        self.assertIn(
            "最终对象统一口径 -> 板块锚反推先选强对象，小账户资金取舍再定资金优先，最后只生成明日唯一动作或观察对象",
            context["field_mappings"],
        )
        self.assertIn(
            "最终对象角色拆分 -> new_entry_target新开仓对象 / existing_position_target旧仓处理对象 / tradable_proxy_target小资金可交易替代表达 / watch_target观察对象 / process_target过程对象 / display_target最终动作显示对象",
            context["field_mappings"],
        )
        self.assertIn(
            "Wiki口径边界 -> LLM Wiki沉淀统一输出口径，运行代码生成final_target_resolution，报告模块只消费该结果不各自重算标的",
            context["report_boundaries"],
        )
        self.assertIn("板块锚反推", flows)
        self.assertIn("小账户资金取舍", flows)
        self.assertIn("final_target_resolution", flows)
        self.assertIn("tradable_proxy_target: 小资金可交易替代表达", flows)
        self.assertIn("display_target: 明日唯一动作或观察对象", flows)
        self.assertIn("只消费final_target_resolution，不各自重算标的", flows)

    def test_wiki_records_cull_weak_keep_strong_capital_priority(self):
        context = build_llm_wiki_context()
        field_mappings = context["field_mappings"]
        digest = context["report_digest_text"]
        price_wiki = (ROOT / "wiki/交易思想/价格行为与能量框架.md").read_text(encoding="utf-8")
        t_wiki = (ROOT / "wiki/交易思想/做T与风险控制.md").read_text(encoding="utf-8")

        for required in [
            "汰弱留强",
            "汰强留弱",
            "旧仓和新机会必须分开判断",
            "长电科技 or 华电辽能",
            "不是单纯观察新票",
            "先问旧仓是否仍被资金选择",
            "最后才决定资金优先级",
            "做T便利性替代市场选择",
            "09:30-09:35、09:50-10:10 或 14:30-14:55",
            "MA/VWAP/0轴承接",
            "仓位上限和失效条件",
            "MA5 < MA7",
            "先按短线下跌排列处理",
            "站回 MA7，放量大阳",
        ]:
            self.assertIn(required, price_wiki)

        for required in [
            "做T不能成为留弱票或补弱票的理由",
            "旧仓仍强才用做T优化成本",
            "旧仓走弱就先处理风险",
            "t_not_weak_rescue",
            "做T不是救弱票",
        ]:
            self.assertIn(required, t_wiki)

        self.assertIn(
            "汰弱留强 -> 资金优先留给仍被市场选择、承接和执行条件更清楚的对象；旧仓失效先处理，新机会必须独立确认",
            field_mappings,
        )
        self.assertIn(
            "旧仓新机会分离 -> 先判旧仓是否仍有持仓或做T资格，再判新机会是否更强且窗口和亏损边界清楚，最后决定资金优先级",
            field_mappings,
        )
        self.assertIn(
            "MA5低于MA7弱排列 -> 先按下跌中继或弱修复观察，不给主买/补位资格；只有站回MA7、放量大阳、收在高位且强板块同步，才恢复比较资格",
            field_mappings,
        )
        self.assertIn(
            "结构性吸血行情 -> 指数强但多数个股弱时，先承认资金集中在强主线；旧方向日内反弹不等于风格切换",
            field_mappings,
        )
        self.assertIn(
            "旧方向右侧确认 -> 超跌反弹后回落不再创新低、底部抬高，才恢复短线波段观察；继续新低只按弱反弹处理",
            field_mappings,
        )
        self.assertIn(
            "强主线内部轮动 -> AI硬件等强主线高潮后，优先找紧缺环节和新技术的内部轮动，不先假设大切换",
            field_mappings,
        )
        self.assertIn(
            "龙头资格反推 -> 涨停/T字板只是资金表态证据，必须通过板块锚、承接路径、相对强弱和可执行窗口反推；观察样本不能顶掉龙头",
            field_mappings,
        )
        self.assertIn("汰弱留强新旧", digest)
        self.assertIn("MA5<MA7先弱", digest)
        self.assertIn("结构吸血主线", digest)
        self.assertIn("旧反弹非切换", digest)
        self.assertIn("轮动找紧缺", digest)
        self.assertIn("T字先反推", digest)

    def test_article_cognition_gap_rules_enter_llm_wiki(self):
        context = build_llm_wiki_context()
        field_mappings = context["field_mappings"]
        digest = context["report_digest_text"]
        price_wiki = (ROOT / "wiki/交易思想/价格行为与能量框架.md").read_text(encoding="utf-8")
        sector_wiki = (ROOT / "wiki/板块补充/板块中枢与主线延续.md").read_text(encoding="utf-8")

        for required in [
            "情绪异动两日验证",
            "连续实体阴线",
            "最后一杀",
            "资金切换到新线路",
            "超跌反弹只按短套利预期",
        ]:
            self.assertIn(required, price_wiki)

        for required in [
            "线路代表不是买入名单",
            "彩蛋只作为线路代表",
            "爆发后顺着同线找龙2、龙3",
            "鱼尾行情只看核心",
            "后排补涨一旦承接散掉",
            "早信、鱼身与后手风险",
            "早信不是早买",
            "无人问津不是没涨",
            "主动卖飞是能力",
        ]:
            self.assertIn(required, sector_wiki)

        self.assertIn(
            "情绪异动两日验证 -> 大众情绪剧烈波动后先写两日验证；连续实体阴线按最后一杀观察，异动后直接大阳按资金切到新线路观察",
            field_mappings,
        )
        self.assertIn(
            "超跌反弹预期 -> 跌多只给短套利预期；未出现趋势反转和资金回流前，不把反弹升级为新趋势",
            field_mappings,
        )
        self.assertIn(
            "鱼尾后排风险 -> 加速末端只看核心承接；补涨和后排只能作反馈，承接散掉先杀后排",
            field_mappings,
        )
        self.assertIn(
            "线路代表 -> 彩蛋和候选只代表资金可能切换的线路，爆发后顺着同线找龙2、龙3，不把名单当买入名单",
            field_mappings,
        )
        self.assertIn(
            "早信不是早买 -> 龙头或分支二次发力只提高观察优先级；买入资格仍看固定交易窗口、板块同步、个股承接、亏损边界和失效条件",
            field_mappings,
        )
        self.assertIn(
            "无人问津定义 -> 核心已经给出资金信号但板块多数载体未充分反应，不是纯下跌、便宜或没涨过",
            field_mappings,
        )
        self.assertIn(
            "鱼身位置 -> 只参与信号确认后到人声鼎沸前的中段；先涨者转弱、补涨扩散或权重拉指数时主动降风险",
            field_mappings,
        )
        self.assertIn("情绪异动后看两日验证", digest)
        self.assertIn("超跌反弹只按短套利", digest)
        self.assertIn("鱼尾只看核心不追后排", digest)
        self.assertIn("彩蛋是线路代表不是买入名单", digest)

    def test_supply_chain_bottleneck_framework_enters_llm_wiki(self):
        context = build_llm_wiki_context()
        field_mappings = context["field_mappings"]
        flows = "\n".join(context["process_flows"])
        digest = context["report_digest_text"]
        wiki_text = (ROOT / "wiki/板块补充/供应链瓶颈研究法.md").read_text(encoding="utf-8")

        for required in [
            "Serenity / @aleabitoreddit",
            "用 AI 拆产业链，而不是让 AI 直接推荐股票",
            "供应链瓶颈研究",
            "AI 的价值不是给结论，而是提高研究量上限",
            "不是看谁最强，而是看谁不可替代",
            "从下游往上游倒推",
            "公开信息背后的结构信息",
            "噪音归零，等证据验证",
            "宏观看空，微观做多",
            "industry_chain",
            "bottleneck_layer",
            "thesis_broken_conditions",
            "供应链瓶颈只能提高研究优先级，不能单独生成买入资格",
            "不把粉丝版 skill 当作本人官方授权",
        ]:
            self.assertIn(required, wiki_text)

        self.assertIn(
            "供应链瓶颈研究 -> 先拆产业链，再定位材料、工艺、设备、认证、产能或客户锁定形成的关键瓶颈",
            field_mappings,
        )
        self.assertIn(
            "瓶颈股研究候选 -> 只提高研究优先级，不直接生成买入资格；交易动作仍回到价格承接、板块选择、账户适配和失效条件",
            field_mappings,
        )
        self.assertIn(
            "外部大神方法转本地规则 -> 先做来源保真，再做系统化抽象，不保留收益宣传或本人官方授权假设",
            field_mappings,
        )
        self.assertIn(
            "卡脖子三问 -> 先问行业扩张卡在哪里、谁控制瓶颈、市场是否已充分定价，不先问股票代码",
            field_mappings,
        )
        self.assertIn(
            "下游倒推上游瓶颈 -> 显眼龙头只作需求源，继续追材料、工艺、认证、产能、设备和上游处理能力",
            field_mappings,
        )
        self.assertIn(
            "噪音归零验证 -> 瓶颈假设、客户验证、产能兑现和财报方向未破时，不用短期评论替代证据；证据破坏就降级",
            field_mappings,
        )
        self.assertIn(
            "宏观看空微观做多 -> 总市场风险决定动作敏感度，个体赢家仍按瓶颈证据、价格承接和板块选择单独研究",
            field_mappings,
        )
        self.assertIn("供应链瓶颈研究 ASCII 流程图", flows)
        self.assertIn("显眼龙头/需求源 -> 平台/模块 -> 激光器/芯片 -> 衬底/材料 -> 上游处理", flows)
        self.assertIn("全球关键供应商 -> A股直接映射 -> A股间接映射", flows)
        self.assertIn("研究线索、板块锚或候选比较字段", flows)
        self.assertIn("供应链先拆瓶颈再验不可替代", digest)
        self.assertIn("研究线索不直接生成买入资格", digest)
        self.assertIn("三问倒推上游", digest)
        self.assertIn("噪音归零看财报", digest)
        self.assertIn("宏空微多找赢家", digest)

    def test_brooks_price_action_trend_rules_enter_llm_wiki(self):
        context = build_llm_wiki_context()
        field_mappings = context["field_mappings"]
        wiki_text = (ROOT / "wiki/交易思想/布鲁克斯价格行为趋势.md").read_text(encoding="utf-8")
        spec_text = (ROOT / "docs/trellis/specs/2026-06-11-brooks-price-action-a-share-volume-design.md").read_text(encoding="utf-8")

        for required in [
            "布鲁克斯价格行为趋势",
            "价格趋势优先",
            "指标组合不能凌驾常用K线",
            "A股量价本地化",
            "叙事后置",
            "成交量是资金表态",
            "放量只是资金表态；价格没有强收盘、回踩不破和后续行情时，只提高观察级别，不生成买入资格。",
            "趋势区间谱系",
            "后续行情确认",
            "始终入场方向",
            "二次入场确认",
            "形态失败燃料",
            "交易者等式",
            "对我的交易启发",
            "0轴、均线、前高、涨停、题材发酵都只是观察信号，不是买入资格",
            "布鲁克斯式触发不是任意一根K线高点更高就买，而是在合适背景下突破前一根信号K线高点后，市场继续给出后续行情；没有背景时，创新高也可能只是反抽。",
            "不在亏损后按图索因，也不在想买时按因索图",
            "A股还要叠加 T+1、涨跌停、账户一手金额、公告风险、板块主线和交易窗口",
        ]:
            self.assertIn(required, wiki_text)

        for required in [
            "布鲁克斯价格趋势优先 -> 所有走势最终反映到价格趋势；先看价格趋势、常用K线和收盘位置，指标组合只作辅助证据",
            "布鲁克斯A股量价本地化 -> 价格是最终裁判，成交量是资金表态；量先用于识别谁在行动，参与资格必须由价格后续确认",
            "叙事后置 -> 资金、消息、基本面和量化解释都必须反馈到图上；先看趋势、承接、跟随、失败和失效线，原因只解释背景不替代参与资格",
            "量价四象限 -> 放量上涨强收盘看进攻，放量冲高回落看分歧，缩量回踩趋势未破等二次确认，放量破位先处理风险",
            "低位突放巨量 -> 只提高研究和观察优先级，必须等后续行情，不直接生成买入资格",
            "布鲁克斯趋势区间谱系 -> 先判强趋势/普通趋势/宽幅通道/交易区间，再决定顺势、等待还是只观察",
            "布鲁克斯后续行情确认 -> 单根K线、0轴、MA和涨停只触发观察；承接、强收盘和不快速跌回只能进入复盘和下一份日报，不能盘中生成新增参与",
            "始终入场方向 -> 错过强趋势早期买点后，只能用小仓位、同一失效线和同一风险预算参与，不用满仓追涨补偿",
            "二次入场确认 -> 更差价格常是为更高确认度付出的成本；所谓二次机会更便宜时先怀疑趋势转弱",
            "形态失败燃料 -> 失败突破、失败反转和失败回踩会套住交易者，止损和反手可能给相反方向提供动力",
            "交易者等式 -> 参与前说清成功概率、目标空间、失败损失和账户伤害，说不清只观察",
            "图形美学 -> 假底先按反抽看；真正的进攻雏形通常是小K线、缩量横盘、重心上移、靠近前高，最终等阳包阴或突破阳线确认",
        ]:
            self.assertIn(required, field_mappings)

        for required in [
            "Brooks Price Action And A-Share Volume Localization",
            "Brooks A-share Volume-Localized Selection Flow",
            "volume_is_capital_expression",
            "volume_first_for_attention_not_action",
            "Volume expansion + rising price + strong close + sector sync",
            "Volume expands -> funds expressed interest -> check price consequence",
            "N6 反推龙头",
            "龙头反向辩论",
            "A股量价本地化",
            "共同选择一致性",
            "final_target_resolution",
        ]:
            self.assertIn(required, spec_text)

    def test_anti_fake_precision_principle_enters_llm_wiki(self):
        context = build_llm_wiki_context()
        field_mappings = context["field_mappings"]
        wiki_text = (ROOT / "wiki/交易思想/反伪精确第一性原理.md").read_text(encoding="utf-8")

        for required in [
            "事实数值可以保留",
            "主观交易判断不能伪装成精确分数",
            "排序必须来自条件链",
            "板块资金扩散找被资金反复参与的资金载体",
            "好股不一定每天涨停",
            "量化时代的可用缝隙",
            "缺少关键证据时，结论是观察或不参与",
            "不能只写“淘汰了”",
            "本轮按条件链排序，不使用主观加权分。",
            "最终对象必须完整通过淘汰赛路径",
        ]:
            self.assertIn(required, wiki_text)

        for required in [
            "反伪精确第一性原理 -> 事实数值保留，主观判断不写成精确分；明日对象按市场板块、角色、反证、价格行为、账户条件逐层淘汰",
            "板块资金扩散找资金载体 -> 日报先判市场资金结构和板块扩散，再找板块内被反复买入和承接的资金载体；涨停、热榜、龙虎榜和分数只作证据，不作自动买入资格",
            "资金载体角色 -> 涨停高标、趋势容量核心、板块锚/中军、分支龙头都可观察；好股不一定每天涨停，但必须证明资金反复参与、回撤有人接、放量不崩、缩量不死",
            "唯一明日动作 -> 量化参与痕迹和价格行为确认后，还要经过反证、账户、盈亏比和时间窗口，最后只输出一个动作或观察结论",
            "条件链优先 -> 排序必须来自可见事实、合理推断、反方证据和明日动作，不用加权总分替代解释",
            "证据不足处理 -> 没有价格接受或反证解除时，不取得新增参与资格，只观察恢复条件",
        ]:
            self.assertIn(required, field_mappings)

    def test_change_companion_docs_contract_enters_llm_wiki_context(self):
        context = build_llm_wiki_context()
        wiki_text = (ROOT / "wiki/运行契约/LLM Wiki维护与路由契约.md").read_text(encoding="utf-8")
        readme_text = (ROOT / "wiki/README.md").read_text(encoding="utf-8")

        for required in [
            "需求变更与日报伴随文档",
            "AGENTS.md",
            "flow.md",
            "testing.md",
            "readme.md",
            "为什么选中它、为什么没选别人、在哪一步退出",
            "reports/<日期>_A股日报_伴随文档/",
            "reports/replay/<日期>_A股日报_伴随文档_replay/",
        ]:
            self.assertIn(required, wiki_text)

        self.assertIn("AGENTS.md` / `flow.md` / `testing.md` / `readme.md", readme_text)
        self.assertIn(
            "变更伴随文档 -> 每次需求变更和每次生成日报时，同步生成AGENTS.md、flow.md、testing.md、readme.md四个伴随文件；日报伴随目录随reports/replay路径落盘，不写项目根目录；必须能复盘边界、流程、验证和入口",
            context["field_mappings"],
        )


if __name__ == "__main__":
    unittest.main()
