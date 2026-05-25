import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _m(*parts):
    return "".join(parts)

from knowledge.llm_wiki_context import build_llm_wiki_context


class LlmWikiContextTest(unittest.TestCase):
    def test_build_llm_wiki_context_materializes_compact_chinese_nodes(self):
        context = build_llm_wiki_context()

        self.assertEqual(context["version"], "2026-05-26")
        self.assertEqual(context["source"], "llm_wiki")
        self.assertEqual(context["language"], "zh-CN")
        self.assertIn("wiki/交易思想/缠论体系.md", context["source_paths"])
        self.assertIn("wiki/交易思想/价格行为与能量框架.md", context["source_paths"])
        self.assertIn("wiki/交易思想/启动板与趋势持股短板.md", context["source_paths"])
        self.assertIn("wiki/交易思想/极度看好参与时机.md", context["source_paths"])
        self.assertIn("wiki/交易思想/交易错题本.md", context["source_paths"])
        self.assertIn("wiki/交易思想/新股周期与市场情绪.md", context["source_paths"])
        self.assertIn("wiki/交易思想/扣分系统与动作分层.md", context["source_paths"])
        self.assertIn("wiki/交易思想/实际账户情况.md", context["source_paths"])
        self.assertEqual(context["source_paths"].count("wiki/交易思想/扣分系统与动作分层.md"), 1)
        self.assertIn("wiki/交易思想/判断样本与市场演变.md", context["source_paths"])
        self.assertIn("wiki/交易思想/AI摩擦与知识复利.md", context["source_paths"])
        self.assertIn("wiki/板块补充/板块中枢与主线延续.md", context["source_paths"])
        self.assertIn("wiki/交易思想/日报术语契约.md", context["source_paths"])
        self.assertIn("wiki/运行契约/日报数据源契约.md", context["source_paths"])
        self.assertIn("wiki/运行契约/snap-ui发布契约.md", context["source_paths"])
        self.assertIn("日线结构中枢定环境 -> 参与窗口分层确认 -> 30分钟止损", context["field_mappings"])
        self.assertIn("普通结构确认 -> 60分钟确认；强核心快路径 -> 竞价表态、开盘前几分钟或回封", context["field_mappings"])
        self.assertIn("参与时机 -> open_core开盘核心 / ten_confirm 10点确认 / tail_exception尾盘14:30-14:55例外 / no_trade不交易", context["field_mappings"])
        self.assertIn("买卖窗口期 -> 只在09:30-09:35、09:50-10:10、14:30-14:55三段处理买卖；窗口外不新增买卖动作，只等待下一窗口或处理既定风险", context["field_mappings"])
        self.assertIn("统一来源 -> 日报写入decision-ledger planned_participation，snap-ui只消费不重算", context["field_mappings"])
        self.assertIn("极度看好复盘 -> 日报生成时用行情表回写participation_review，封死买不到不算收益命中", context["field_mappings"])
        self.assertIn("明日主买对象 -> 非0%且参与资格成立时给1只主买和1只补位；最终0%时统一降为候选观察", context["field_mappings"])
        self.assertIn("前台收口 -> 0%不参与、唯一对象暂无或只给观察资格时，所有明日动作面板只写观察，不写主买补位或新增参与", context["field_mappings"])
        self.assertIn("狙击手推导顺序 -> 先判退潮，再取候选，再做最终风险复核，再判龙头速度档和买卖线，最后比较共同选择一致性", context["field_mappings"])
        self.assertIn("龙头速度档 -> 极致加速看MA3/MA5，高弹性强趋势看MA5/MA10，大容量趋势看MA10/MA20", context["field_mappings"])
        self.assertIn("共同选择一致性 -> 昨日持筹者不急卖、明日新买盘愿意接、主线资金仍有理由选择", context["field_mappings"])
        self.assertIn("心理价位与量化锚点 -> 对子数、整数位、前高前低、VWAP、MA和成交密集区只作价格锚点，不作独立买入理由", context["field_mappings"])
        self.assertIn("隐藏买卖盘 -> 顶部锚点冲不过按隐藏卖盘和止盈观察，底部锚点必须站回VWAP并完成10点确认才允许试错", context["field_mappings"])
        self.assertIn("量化共同选择 -> 昨日持筹者、明日新买盘、主线资金、量化动量四方一致后才提高参与质量", context["field_mappings"])
        self.assertIn("高潮反包 -> 高潮后反包优先按先手兑现点，放量吃掉压力并回踩不破才恢复候选", context["field_mappings"])
        self.assertIn("最终风险复核 -> 公告风险、连续长上影未修复、跌破对应卖点线收不回，取消主买和补位资格", context["field_mappings"])
        self.assertIn("趋势审美复核 -> 明日极度看好先看近120日日K，上升趋势/平台震荡/缩量回踩有承接才保留；A杀/放量下杀/反抽不过关键线/高低点下移只观察", context["field_mappings"])
        self.assertIn("选股形态审美 -> 先看120日日K的呼吸感、蛇形走位、重心上移、平台消化和缩量回踩；A杀、破位弱反抽、放量下杀不参与", context["field_mappings"])
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
        self.assertIn("结构止损 -> 个股3%-5%浮亏先检查买入理由，结构破坏才处理，个股-10%是事故极限", context["field_mappings"])
        self.assertIn("账户伤害 -> 止损看个股结构，伤害看账户本金，普通波动不能打残账户", context["field_mappings"])
        self.assertIn("攻击频次 -> 没有防守边界的高频进攻会把收益对冲成无效波动", context["field_mappings"])
        self.assertIn("亏损边界 -> 先避免大亏损，再追求偶尔向上大盈利", context["field_mappings"])
        self.assertIn("胜率赔率 -> 胜率接近天花板时用大赚小亏和利润奔跑修复期望", context["field_mappings"])
        self.assertIn("赚钱效应退潮 -> 单边趋势道寻常，震荡退潮期降低攻击频次和预期收益", context["field_mappings"])
        self.assertIn("震荡市短线波段 -> 连跌后只允许轻仓低吸，反弹先卖回，不把低吸扩成满仓趋势持有", context["field_mappings"])
        self.assertIn("趋势股越跌越减 -> 针对追高且图形走弱的趋势仓；沿均线上行可持有，图形破坏反弹减亏", context["field_mappings"])
        self.assertIn("均线执行锚点 -> MA3/MA5/MA10/MA20用于识别震荡区间的反弹、回落和趋势破坏，不替代交易理由", context["field_mappings"])
        self.assertIn("量化看图 -> 技术图形、成交数据和消息会放大线位反应，只作执行环境不作买入理由", context["field_mappings"])
        self.assertIn("消息归因降权 -> 除个股直接风险外，消息只确认风险，不生成买点，不替代价格量能承接和仓位判断", context["field_mappings"])
        self.assertIn("集中大赚 -> 必须先写代价和平衡，不能把追求大赚变成无边界押注", context["field_mappings"])
        self.assertIn("AI摩擦与知识复利 -> 消除低效摩擦后必须补上反馈机制；复利方向由接入过程决定，知识节点碰撞形成个人护城河", context["field_mappings"])
        self.assertIn("必要认知摩擦 -> AI生成后至少复述、重写、对比或沉淀成知识节点，避免只复制结果", context["field_mappings"])
        self.assertIn("板块节奏 -> 量化环境下先看板块路径和资金选择，再看单一龙头定价", context["field_mappings"])
        self.assertIn("窄池子进攻 -> 指数强但上涨家数弱时，不按普涨处理，先看资金集中选择哪些板块路径", context["field_mappings"])
        self.assertIn("量化仍在 -> 板块成交占比维持或扩张、板块宽度扩散、核心承接稳定、竞争方向掉队", context["field_mappings"])
        self.assertIn("量化离场 -> 成交占比回落、后排掉队、核心跌回VWAP或关键均线，三项共振时先退出", context["field_mappings"])
        self.assertIn("迹象识别链 -> 从反复出现的市场迹象提炼现象规律，再在实战中识别、验证和主动运用，不把单次巧合当规律", context["field_mappings"])
        self.assertIn("相对优势进攻 -> 等弱方向开始掉队、强方向仍有资金扩散和核心承接时，才从观察进入参与", context["field_mappings"])
        self.assertIn("主战场能力圈 -> 短线/超短线追求500强水平；趋势容量、机构抱团和慢推行情只求不拖后腿", context["field_mappings"])
        self.assertIn("非主战场纪律 -> 低适配行情不扩战法，不为证明全能而新增参与", context["field_mappings"])
        self.assertIn("资金阶段 -> 小资金允许追求高弹性，但只做市场承认的热门核心，不做随机高波动", context["field_mappings"])
        self.assertIn("小资金优势校准 -> 小资金优势是灵活切换核心，不是频繁乱动或救错误仓", context["field_mappings"])
        self.assertIn("AI辅助边界 -> AI负责筛核心、拦错误、做复盘，不承诺省心躺赚", context["field_mappings"])
        self.assertIn("热门妖股 -> 价格、成交、辨识度、板块地位共同确认的核心，不是听来的故事票", context["field_mappings"])
        self.assertIn("辨识度优先 -> 高弹性交易优先选择市场共识最强的核心标的，宁可少做不做边缘票", context["field_mappings"])
        self.assertIn("新股辨识度 -> 新股身份不是辨识度，只有盟固利/无线传媒式情绪旗帜才升级为核心", context["field_mappings"])
        self.assertIn("趋势容错 -> 上升趋势/短期周期未破时容错高，下降趋势/周期破坏时容错低", context["field_mappings"])
        self.assertIn("周期持有 -> 短线按博弈周期判断，周期未破可持有，周期破坏先退出", context["field_mappings"])
        self.assertIn("买点卖点底层操作 -> MA3攻击线 / MA7分歧线 / MA10认错线 / MA20环境线", context["field_mappings"])
        self.assertIn("点位依据声明 -> 盘中买卖点必须说明来自MA组合、VWAP、开盘价、前高前低、成交密集区或形态脚本，无来源区间不作决策", context["field_mappings"])
        self.assertIn("形态交易脚本 -> 上升趋势顺势回踩，下降趋势只做右侧确认，V/M/W/A按确认与破坏执行", context["field_mappings"])
        self.assertIn("紧急止损规则 -> 收盘同破MA7/MA10、放量大跌超7%、连续3日MA3下方、MA20下拐", context["field_mappings"])
        self.assertIn("成交量确认 -> 放量破位优先信风险，缩量破位必须看能否收回", context["field_mappings"])
        self.assertIn("指数价跌量增 -> 指数或全市场大跌且两市成交额放大，优先按卖压释放、量化踩踏或出货风险处理", context["field_mappings"])
        self.assertIn("放量杀跌局部强势 -> 只按逆势试攻或观察主攻线，等指数止跌、跌停收敛和主攻线连续承接后再恢复评估", context["field_mappings"])
        self.assertIn("价格带风格 -> 百元股涨跌幅减低价股涨跌幅，-2pct以下冰点，-2pct到+2pct震荡，+2pct以上高潮", context["field_mappings"])
        self.assertIn("创新高趋势 -> 非ST非新股非次新250日新高占全A比例，2%以下冰点，2%到5%震荡，5%以上高潮", context["field_mappings"])
        self.assertIn("创新高用法 -> 只作资金扩散方向雷达，权重封顶；不直接生成个股买点，参与仍看趋势审美、承接、回踩质量和作废线", context["field_mappings"])
        self.assertIn("市场情绪总状态 -> 先看盘面亏钱效应，指数大跌、跌多涨少、跌停扩散时，局部指标高潮只能写局部过热，整体高潮必须亏钱效应不重、热度扩散强、方向确认强", context["field_mappings"])
        self.assertIn("时间窗口偏好 -> 买卖只认09:30-09:35、09:50-10:10、14:30-14:55三段；尾盘不再拆其他子窗口", context["field_mappings"])
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
        self.assertIn("候选质量评分 -> 先挣分、再扣分、再动作上限；分数服务排序，动作上限决定最多能做什么", context["field_mappings"])
        self.assertIn("今日总决策面板 -> 市场情绪、账户后台任务负担、今日新增上限、持仓优先动作、主买对象、补位对象、禁止动作和忽略清单先于单票评分", context["field_mappings"])
        self.assertIn("候选主表 -> 当前持仓、可卖数量、不可卖数量、仓位性质、账户状态、计划仓位档、实际仓位、仓位偏离、周期身份、选股质量、买点质量、风险项、成本项、动作上限、持仓动作、新开仓动作、恢复条件、取关条件、最晚复核", context["field_mappings"])
        self.assertIn("账户状态 -> 实际可买/实际不可买；只决定账户是否参与，不改变市场核心、池内身份或周期身份", context["field_mappings"])
        self.assertIn("仓位表达 -> 计划仓位档记录0/50/100策略意图，实际仓位记录一手颗粒度后的账户落点，仓位偏离说明低配或超配", context["field_mappings"])
        self.assertIn("半仓颗粒度 -> 一手实际占用40%-60%仍按50%档，不升满仓也不降观察；决策看档位，账户看实际", context["field_mappings"])
        self.assertIn("选股买点拆分 -> 好票高成本保护选股资格但不追高；差票低成本的MA/VWAP只作已有仓处理参考", context["field_mappings"])
        self.assertIn("后台任务负担 -> 未处理风险仓会占用注意力，先处理持仓风险再看新增机会，高负担时不新增参与", context["field_mappings"])
        self.assertIn("动作五层 -> 主买、补位、核心观察、修复观察、不参与；持仓动作和新开仓动作分开输出", context["field_mappings"])
        self.assertIn("盘中问股继承 -> 先读前一晚动作层级和今日新增上限；不参与不能直升主买或补位，观察类只在恢复条件命中后上调", context["field_mappings"])
        self.assertIn("复盘校准 -> 记录当时判断、实际走势、买点出现、用户偏离、错误归因和样本保护结果；不因单个收益结果自动调权重", context["field_mappings"])
        self.assertIn("样本保护 -> 规则变更必须同时检查核心机会、差票低成本和好票高成本样本，不能为修边角破坏大机会", context["field_mappings"])
        self.assertIn("恢复取关复核 -> 每个观察样本必须写恢复条件、取关条件和最晚复核时间，避免观察变成后台任务", context["field_mappings"])
        self.assertIn("禁止清单 -> 不该做什么优先级高于想买什么，先拦错再谈进攻", context["field_mappings"])
        self.assertIn("来源保真 -> 区分原文可支持、系统化抽象、不能归因给原文", context["field_mappings"])
        self.assertIn("新股周期 -> 市场周期、新股扩散、首日情绪、C阶段承接、情绪出口地位", context["field_mappings"])
        self.assertIn("新股样本 -> 盟固利是弱市投机宣泄；无线传媒是强修复情绪出口；历史相似不能替代当前承接验证", context["field_mappings"])
        self.assertIn("风格切换 -> 主升后震荡分歧先看轮动、回流、题材活跃和连板晋级率", context["field_mappings"])
        self.assertIn("赛道题材 -> 赛道看产业持续性，题材看概念催化，二者没有好坏但执行节奏不同", context["field_mappings"])
        self.assertIn("板块叙事迁移 -> 表层行业标签要服从当日资金叙事，汽车零部件/电机在机器人语境下按人形机器人辅助判断", context["field_mappings"])
        self.assertIn("龙头回头复核 -> 低位反馈不能替代龙头顶住压力；龙头二次确认和低位/中位反馈同时出现，才记录为市场继续投票", context["field_mappings"])
        self.assertIn("科技震荡 -> 总体调整中只做聚焦参与，快进快出，低于预期先处理", context["field_mappings"])
        self.assertIn("科技支线容量条件 -> 容量参考线随当前成交额分布校准，还要看科技成交、扩散和核心承接", context["field_mappings"])
        self.assertIn("注意力发酵节点 -> 产业逻辑被集中讨论且走势仍在初期，才按支线波段观察", context["field_mappings"])
        self.assertIn("紧缺叙事 -> 支线催化优先看主线环节供需紧张，但不能替代价格承接", context["field_mappings"])
        self.assertIn("稳定知识写入 LLM Wiki", context["write_boundaries"])
        self.assertIn("原文不直接进入日报主链", context["report_boundaries"])
        self.assertIn("MACD只能作为辅助", context["report_boundaries"])
        self.assertIn("用户可见输出不用旧工程口径，改用资格/条件/可做/参与/不参与", context["report_boundaries"])
        self.assertIn("fresh daily generation uses Tushare-first", context["data_source_policy"])
        self.assertIn("akshare/iwencai are fallback only", context["data_source_policy"])
        self.assertIn("snap-ui publish verifies Cloudflare module assets before push", context["publish_policy"])
        self.assertIn("develop is the Cloudflare Pages branch", context["publish_policy"])

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
            "重点观察25日跟踪表",
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

        self.assertIn(
            "资金载体错配 -> 叙事、核心锚、弹性载体和参与资金不在同一周期时，不能用统一持股剧本",
            context["field_mappings"],
        )
        self.assertIn(
            "新题材早信/不信 -> 真新题材只在早期主动性和第一确认窗口提高参与质量，后手只观察或等分歧确认",
            context["field_mappings"],
        )
        self.assertIn("先判断买的是产业趋势、核心锚、量化弹性还是情绪后排", digest)

    def test_build_llm_wiki_context_exposes_knowledge_compounding_candidates(self):
        context = build_llm_wiki_context()

        candidates = context.get("knowledge_compounding_candidates")
        self.assertIsInstance(candidates, list)
        self.assertEqual(len(candidates), 1)

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

    def test_build_llm_wiki_context_keeps_report_digest_short_and_fieldized(self):
        context = build_llm_wiki_context()
        digest = context["report_digest_text"]

        self.assertIn("角度与幅度", digest)
        self.assertIn("价格是裁判", digest)
        self.assertIn("资金流和指标只作辅助", digest)
        self.assertIn("消息只确认风险不生成买点", digest)
        self.assertIn("先用量能、情绪、板块、资金、辨识度和承接决定买卖资格", digest)
        self.assertIn("MA3/MA5/MA10只做执行锚点", digest)
        self.assertIn("该涨不涨按时间消耗风险降级", digest)
        self.assertIn("低回撤和稳定复利优先", digest)
        self.assertIn("日赚1%不是稳定目标", digest)
        self.assertIn("月度15%-20%是攻击目标不是每日交易要求", digest)
        self.assertIn("小资金盈利模式靠少数高质量核心机会", digest)
        self.assertIn("轻仓试错确认后加冲高分批卖破结构减", digest)
        self.assertIn("3%-5%浮亏先检查买入理由", digest)
        self.assertIn("结构破坏才处理个股-10%是事故极限", digest)
        self.assertIn("账户不能被普通波动打残", digest)
        self.assertIn("攻击频次服从亏损边界", digest)
        self.assertIn("先避免大亏再追求大赚", digest)
        self.assertIn("胜率难绝对统治时靠赔率", digest)
        self.assertIn("震荡市连跌轻仓低吸、反弹卖回", digest)
        self.assertIn("趋势股图形走弱越跌越减", digest)
        self.assertIn("MA3/MA5/MA10/MA20只做均线执行锚点", digest)
        self.assertIn("板块节奏优先", digest)
        self.assertIn("指数强上涨家数弱按窄池子", digest)
        self.assertIn("量化仍在看成交占比扩张宽度扩散核心承接", digest)
        self.assertIn("占比回落后排掉队核心跌回VWAP或关键均线先退出", digest)
        self.assertIn("迹象到规律再到实战运用", digest)
        self.assertIn("弱方向掉队强方向扩散承接才参与", digest)
        self.assertIn("短线超短主战场追求500强", digest)
        self.assertIn("非主战场不拖后腿不扩战法", digest)
        self.assertIn("非0%且资格成立才给明日主买1只补位1只", digest)
        self.assertIn("0%无唯一对象只观察", digest)
        self.assertIn("历史表统一观察位窗口", digest)
        self.assertIn("上证缠论明日计划明日抉择同向只观察", digest)
        self.assertIn("速度档", digest)
        self.assertIn("共同选择", digest)
        self.assertIn("对子整数只作锚点", digest)
        self.assertIn("顶部冲不过先止盈", digest)
        self.assertIn("底部站回VWAP和10点确认才试错", digest)
        self.assertIn("反包先按兑现点", digest)
        self.assertIn("公告风险长上影未修复破卖点线取消主买补位资格", digest)
        self.assertIn("趋势审美看120日日K", digest)
        self.assertIn("选股形态看呼吸感蛇形走位", digest)
        self.assertIn("A杀放量下杀反抽不过关键线高低点下移只观察", digest)
        self.assertIn("小资金高弹性只做热门核心", digest)
        self.assertIn("小资金优势是灵活切换核心", digest)
        self.assertIn("AI筛核心拦错误做复盘", digest)
        self.assertIn("辨识度优先", digest)
        self.assertIn("新股身份不是辨识度", digest)
        self.assertIn("买点卖点底层操作", digest)
        self.assertIn("MA3攻击、MA7分歧、MA10认错、MA20环境", digest)
        self.assertIn("盘中点位必须说明MA组合VWAP开盘价前高前低成交密集区或形态脚本来源", digest)
        self.assertIn("V/M/W/A按确认与破坏执行", digest)
        self.assertIn("紧急止损规则", digest)
        self.assertIn("放量大跌超7%", digest)
        self.assertIn("成交量确认", digest)
        self.assertIn("指数价跌量增先防踩踏", digest)
        self.assertIn("局部强势只按逆势试攻", digest)
        self.assertIn("市场情绪总状态先看盘面亏钱效应", digest)
        self.assertIn("局部指标高潮只写局部过热", digest)
        self.assertIn("连续上影破MA5先离场", digest)
        self.assertIn("避坑规则必须带重新参与条件", digest)
        self.assertIn("换仓先证旧仓失效、新仓更强、风险能承受", digest)
        self.assertIn("亏损仓不靠充值加仓摊低成本", digest)
        self.assertIn("前夜计划先定账户状态和禁止清单", digest)
        self.assertIn("实际不可买仍在池只观察强度不参与今日比较", digest)
        self.assertIn("计划仓位档管意图实际仓位管落账", digest)
        self.assertIn("无计划新方向盘中无满仓资格", digest)
        self.assertIn("盘中问股先查公告风险", digest)
        self.assertIn("问答风险源配置到stock_risk_map", digest)
        self.assertIn("每个买卖点说明点位依据", digest)
        self.assertIn("减持强制执行让均线支撑降级", digest)
        self.assertIn("参与窗口分层确认", digest)
        self.assertIn("普通结构才等60分钟确认", digest)
        self.assertIn("强核心开盘核心", digest)
        self.assertIn("10点确认", digest)
        self.assertIn("买卖窗口0930-0935/0950-1010/1430-1455", digest)
        self.assertIn("30分钟止损", digest)
        self.assertIn("资格、条件、可做和参与", digest)
        self.assertLessEqual(len(digest), 1040)
        self.assertNotIn("缠论原文", digest)
        self.assertNotIn("能量学", digest)
        self.assertNotIn("教你炒股票", digest)


if __name__ == "__main__":
    unittest.main()
