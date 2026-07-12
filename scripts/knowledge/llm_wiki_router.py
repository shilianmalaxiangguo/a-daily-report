"""Explainable LLM Wiki routing for daily-report knowledge hits."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List


KNOWLEDGE_INDEX = [
    {
        "id": "market.low-frequency-focus",
        "prior": "market-structure-prior",
        "source_path": "wiki/板块补充/板块中枢与主线延续.md",
        "title": "指数强但赚钱效应弱",
        "topics": ["市场结构", "低频聚焦", "窄池子进攻"],
        "trigger_terms": ["指数上涨", "上涨家数偏弱", "成交集中", "指数强", "跌多涨少"],
        "scenarios": ["daily_report", "review"],
        "report_slot": "市场结构判断",
        "confidence": "verified",
        "impact": "指数强但赚钱效应弱时，只保留主线核心，不从旧方向强行扩散候选。",
    },
    {
        "id": "market.sector-grid-first-selection",
        "prior": "market-structure-prior",
        "source_path": "wiki/板块补充/板块中枢与主线延续.md",
        "title": "水池九宫格与先选板块",
        "topics": [
            "结构性行情",
            "全市场水池",
            "水池九宫格",
            "先选板块",
            "板块网格化",
            "资金水位",
            "蓝色粗水柱",
            "红色细水柱",
            "主线抱团",
            "边角标的",
        ],
        "trigger_terms": [
            "结构性行情",
            "全市场水池",
            "水池九宫格",
            "九宫格",
            "网格化",
            "板块网格化",
            "先选板块",
            "板块先行",
            "资金水位",
            "蓝色粗水柱",
            "红色细水柱",
            "水柱",
            "蓝柱",
            "红柱",
            "主线抱团",
            "机构抱团",
            "短线题材",
            "边角标的",
            "轮动不到",
            "资金灌入",
            "板块格子",
        ],
        "scenarios": ["daily_report", "intraday_question", "candidate_quality", "review"],
        "report_slot": "市场结构判断",
        "confidence": "reviewed",
        "impact": "结构性行情先问资金灌入哪个板块格子，再在格子内区分机构主线、短线题材和边角标的；先选板块不是只看板块名字，而是看成交占比、宽度、核心承接和竞争方向，边角标的不因轮动自动取得参与资格。",
    },
    {
        "id": "account.unbuyable-core-anchor",
        "prior": "account-execution-prior",
        "source_path": "wiki/交易思想/实际账户情况.md",
        "title": "实际不可买不降低市场身份",
        "topics": ["账户", "实际不可买", "市场核心", "候选比较"],
        "trigger_terms": ["实际不可买", "一手金额过高", "账户本金不足", "市场核心", "买不了"],
        "scenarios": ["daily_report", "intraday_question", "candidate_quality"],
        "report_slot": "账户约束",
        "confidence": "verified",
        "impact": "实际不可买只影响当前账户参与，不降低市场核心、池内身份或板块锚价值。",
    },
    {
        "id": "decision.anti-prediction-response-script",
        "prior": "decision-sample-prior",
        "source_path": "wiki/交易思想/判断样本与市场演变.md",
        "title": "反预测崇拜与应对剧本",
        "topics": [
            "预测崇拜",
            "每天一个个股",
            "踩准节拍",
            "应对剧本",
            "量化行为博弈",
            "散户行为模式",
            "第一动作",
            "B1参与权",
            "B2确认权",
        ],
        "trigger_terms": [
            "预测崇拜",
            "每天一个个股",
            "每天一个股",
            "踩准节拍",
            "应对剧本",
            "量化行为博弈",
            "散户行为模式",
            "行为陷阱",
            "第一动作",
            "连接感",
            "B1",
            "B2",
            "B1参与权",
            "B2确认权",
            "0%不参与",
            "无执行目标",
            "只观察",
            "不强行凑个股",
            "买入资格",
            "踏空焦虑",
            "阳线追后排",
            "回本卖出",
            "小赚止盈",
        ],
        "fact_conditions": {
            "must_any": [
                {"path": "decision.position_plan", "contains_any": ["0%不参与", "零仓位"], "label": "0%不参与"},
                {"path": "decision.execution_object_state", "contains_any": ["无执行目标"], "label": "无执行目标"},
                {"path": "decision.action_layer", "contains_any": ["只观察", "观察层"], "label": "只观察"},
                {"path": "decision.participation_rhythm", "contains_any": ["第一动作", "初始动作"], "label": "第一动作"},
                {"path": "decision.behavior_traps", "contains_any": ["踏空焦虑", "阳线追后排", "回本卖出", "小赚止盈"], "label": "行为陷阱"},
            ],
            "prefer_any": [
                {"path": "decision.b1_role", "contains_any": ["参与权", "参与角色"], "label": "B1参与权"},
                {"path": "decision.b2_role", "contains_any": ["确认权", "确认角色"], "label": "B2确认权"},
                {"path": "decision.qualification", "contains_any": ["买入资格", "资格不足"], "label": "买入资格"},
                {"path": "decision.response_mode", "contains_any": ["应对剧本", "应对"], "label": "应对剧本"},
            ],
        },
        "scenarios": ["daily_report", "intraday_question", "candidate_quality", "review"],
        "report_slot": "明日执行结论",
        "confidence": "reviewed",
        "impact": "日报不是预测节拍，而是准备应对剧本；没有买入资格时0%不参与也是有效结论。第一动作只给B1参与权，B2必须等待后续承接、板块扩散和个股强度确认，不能因为踏空焦虑补足。",
    },
    {
        "id": "position.cull-weak-keep-strong",
        "prior": "capital-priority-prior",
        "source_path": "wiki/交易思想/价格行为与能量框架.md",
        "title": "汰弱留强与旧仓新机会分离",
        "topics": ["去弱留强", "汰弱留强", "资金优先级", "旧仓新机会分离", "换仓", "第一性原理", "FOMO"],
        "trigger_terms": [
            "去弱留强",
            "汰弱留强",
            "汰强留弱",
            "卖强补弱",
            "弱替代",
            "浮盈浮亏",
            "换仓",
            "旧仓",
            "新机会",
            "第一性原理",
            "FOMO",
            "fomo",
            "满仓",
        ],
        "scenarios": ["daily_report", "intraday_question", "review"],
        "report_slot": "资金优先级",
        "confidence": "verified",
        "impact": "先判旧仓是否失去持仓资格，卖旧仓看旧仓资格；再判新机会是否取得执行资格，买新仓看新仓资格；不卖强补弱，也不用FOMO把两笔判断合成一次满仓替换。",
    },
    {
        "id": "market.performance-rotation-main-attack",
        "prior": "market-structure-prior",
        "source_path": "wiki/板块补充/板块中枢与主线延续.md",
        "title": "业绩线与战术主攻切换",
        "topics": [
            "业绩线",
            "轮动线",
            "科技线牵制",
            "主攻点切换",
            "风格切换载体",
            "主线战术资源",
        ],
        "trigger_terms": [
            "业绩线",
            "业绩逻辑",
            "业绩超预期",
            "轮动线",
            "科技线",
            "非科技",
            "海外链",
            "国产链",
            "主攻点",
            "牵制点",
            "牵制",
            "哈兰德",
            "挪威",
            "超级巨星",
            "风格变换",
            "风格切换载体",
            "主线真空",
            "不合理的超额收益",
        ],
        "scenarios": ["daily_report", "intraday_question", "candidate_quality", "review"],
        "report_slot": "市场结构判断",
        "confidence": "reviewed",
        "impact": "主线不是信仰位，而是战术资源；科技线调整或拥挤时可降为牵制点，业绩线、轮动线和低位趋势线若出现走势活跃、板块逻辑、价格结构和资金扩散共振，就要进入同权比较。最终0%后，强势样本还要复核是孤立情绪还是风格切换载体。",
    },
    {
        "id": "discipline.fomo-external-stimulus",
        "prior": "trade-discipline-prior",
        "source_path": "wiki/交易思想/价格行为与能量框架.md",
        "title": "FOMO 不是交易指令",
        "topics": ["FOMO", "卖飞", "买回", "情绪隔离", "主力情绪", "薛定谔持股", "必卖日执行"],
        "trigger_terms": [
            "FOMO",
            "fomo",
            "卖飞",
            "买回",
            "反包",
            "主力",
            "情绪",
            "后悔",
            "踏空",
            "薛定谔",
            "必卖",
            "空仓",
            "旧仓",
            "0轴卖",
            "纪律成本",
            "可复制",
            "小亏",
        ],
        "scenarios": ["intraday_question", "review", "daily_report"],
        "report_slot": "交易纪律",
        "confidence": "verified",
        "impact": "FOMO 是外部价格刺激被自己接住后的情绪，不是执行资格；反包先批改情绪反应，不直接批改前一日信息集。必卖日里，反抽、0轴、VWAP和开盘价修复先看作旧仓退出流动性；卖出后第一天因反包、后悔或怕踏空想买回，默认不执行，只能收盘后重新进入 T0 评估。",
    },
    {
        "id": "selection.rhythm-reset-margin-review",
        "prior": "selection-review-prior",
        "source_path": "wiki/交易思想/价格行为与能量框架.md",
        "title": "节奏复位空仓与边际主线复核",
        "topics": [
            "节奏复位空仓",
            "延后确认空仓",
            "错失待批改",
            "公共合理不等于超短边际",
            "边际主线",
            "外盘主线传导",
            "旧信号源批改",
            "跨日一致性复核",
        ],
        "trigger_terms": [
            "节奏踏错",
            "同手同脚",
            "合理空仓",
            "边际主线",
            "节奏复位空仓",
            "延后确认空仓",
            "错失待批改",
            "公共合理不等于超短边际",
            "外盘拉升",
            "外盘存储",
            "美股大回调",
            "美股拉升",
            "存储大涨",
            "旧目标强弩之末",
            "强弩之末",
            "旧信号源批改",
            "周五信号源",
            "周五策略",
            "周一空仓",
            "周一策略",
            "周二再强",
            "周二走强",
            "太极实业",
            "宜宾纸业",
        ],
        "scenarios": ["daily_report", "intraday_question", "candidate_quality", "review"],
        "report_slot": "超短边际节奏复核",
        "confidence": "reviewed",
        "impact": "最终0%不是思考终点；继续批改是防守空仓、节奏复位空仓、延后确认空仓还是错失待批改。周一空仓若来自周五旧信号，必须追溯周五选股、买点、持仓预期和退出纪律；周二再强只算重新比较，不替周五或周一正名。外盘和存储强势默认只作启发，必须完成同链传导和A股确认后才进入T+1复核；过程候选不覆盖最终动作。",
    },
    {
        "id": "discipline.tplus-slot-timeline",
        "prior": "trade-discipline-prior",
        "source_path": "wiki/交易思想/价格行为与能量框架.md",
        "title": "Ta-Te 账户日序时间表",
        "topics": ["Ta-Te", "Ta/Tb/Tc/Td/Te", "日序", "T+2必卖", "空仓", "Td", "Te"],
        "trigger_terms": [
            "Ta",
            "Tb",
            "Tc",
            "Td",
            "Te",
            "Ta-Te",
            "Tabcde",
            "Ta+2",
            "Tb+0",
            "Tb+1",
            "Tc+0",
            "T+2必卖",
            "日序",
            "甘特图",
            "没有Tb",
            "没有Tc",
            "明日Te",
            "五日",
            "全天空仓",
        ],
        "scenarios": ["daily_report", "intraday_question", "review"],
        "report_slot": "持仓日序",
        "confidence": "reviewed",
        "impact": "Ta-Te要表格化呈现账户时间占用：Ta是最远复盘日，Tb/Tc是前两段路径，Td是今日报告日，Te是明日执行日。Te只承接昨晚决定的参与、取消或旧仓降风险；明日标的为空时，Te写只处理旧仓风险或空仓等待B1资格。",
    },
    {
        "id": "intraday.do-t-risk-control",
        "prior": "intraday-question-prior",
        "source_path": "wiki/交易思想/做T与风险控制.md",
        "title": "做T先降风险，确认后买回",
        "topics": ["做T", "风险控制", "买回确认", "点位依据"],
        "trigger_terms": ["做T", "亏损", "反弹", "买回", "更便宜"],
        "scenarios": ["intraday_question", "daily_report", "review"],
        "report_slot": "盘中问股前提",
        "confidence": "verified",
        "impact": "做T先看防守线、止盈线和买回确认，不把更便宜当作更正确。",
    },
    {
        "id": "intraday.same-stock-t-failure-control",
        "prior": "intraday-question-prior",
        "source_path": "wiki/交易思想/做T与风险控制.md",
        "title": "同股T强表态失败处理",
        "topics": ["同股T", "临时2x", "强表态失败", "可卖旧仓", "失败仓", "尾盘卖出边界"],
        "trigger_terms": [
            "同股T",
            "同一只票",
            "同一只股",
            "same_stock_t",
            "1x",
            "2x",
            "临时2x",
            "强表态",
            "诱多",
            "可卖旧仓",
            "底仓",
            "失败仓",
            "跌破VWAP",
            "跌破昨收",
            "跌破MA7",
            "MA7清",
            "尾盘卖出",
            "太极实业",
        ],
        "weak_trigger_terms": ["1x", "2x", "太极实业"],
        "scenarios": ["intraday_question", "daily_report", "review"],
        "report_slot": "同股T处理",
        "confidence": "reviewed",
        "impact": "已有1x且今日目标仍是同一只票时，只按同股T候选处理；强表态存活才允许临时2x，快速跌破VWAP、昨收或MA7且不能收回时，卖出可卖旧仓，新买仓位次日按失败仓处理。尾盘卖出只适用于正常样本，失败样本先保护亏损边界。",
    },
    {
        "id": "intraday.two-b-confirmation-positioning",
        "prior": "intraday-question-prior",
        "source_path": "wiki/交易思想/做T与风险控制.md",
        "title": "2B参与权与确认权",
        "topics": ["2B法", "B1", "B2", "参与权", "确认权", "任务仓", "奖励仓", "态度不是仓位", "确认后加速"],
        "trigger_terms": [
            "2B法",
            "2b",
            "B1",
            "B2",
            "0.5B",
            "FOMO",
            "fomo",
            "迷茫",
            "力不从心",
            "追高",
            "赌性",
            "贪念",
            "参与权",
            "确认权",
            "计划补全",
            "补全计划",
            "完成仓位",
            "B1没赢",
            "B1未赢",
            "B2不存在",
            "任务仓",
            "奖励仓",
            "下跌补仓",
            "走弱补仓",
            "必须买够",
            "买够",
            "怕小赚",
            "小赚",
            "少赚",
            "少亏",
            "少亏少赚",
            "大赚",
            "复利",
            "态度",
            "仓位",
            "集合竞价买一半",
            "确认后加速",
            "初始仓位",
        ],
        "scenarios": ["intraday_question", "daily_report", "review"],
        "report_slot": "2B仓位处理",
        "confidence": "reviewed",
        "impact": "B1只买参与权，B2只买确认权；B2不是任务仓，没有确认就没有补足义务。交易计划不是仓位完成任务，而是确认、取消和降风险的筛选器；B1没赢之前，B2不存在。短线超额来自确认后加速，不来自所有样本开盘买满；坏样本只亏B1，好样本才给B1+B2。少亏不是畏手畏脚，而是长期跑赢的一部分。",
    },
    {
        "id": "discipline.profit-after-win-control",
        "prior": "trade-discipline-prior",
        "source_path": "wiki/交易思想/做T与风险控制.md",
        "title": "盈利后失控与顺境收紧",
        "topics": ["盈利后失控", "顺境收紧", "连续盈利", "两笔出问题停手", "活跃资金风向标"],
        "trigger_terms": [
            "连续盈利",
            "盈利后",
            "赚了以后",
            "飘了",
            "失控",
            "两笔出问题",
            "直接停手",
            "股池",
            "连板高度",
            "热点宽度",
            "活跃股梯队",
            "高位异动",
        ],
        "scenarios": ["daily_report", "intraday_question", "review"],
        "report_slot": "交易纪律",
        "confidence": "reviewed",
        "impact": "连续盈利后先降频降仓并复核规则；两笔预演不顺或触发失效直接停手，恢复参与要看活跃资金和股池强者修复。",
    },
    {
        "id": "candidate.quality-action-layer",
        "prior": "candidate-quality-prior",
        "source_path": "wiki/交易思想/扣分系统与动作分层.md",
        "title": "候选质量条件链与动作上限",
        "topics": ["候选质量", "动作层级", "恢复条件", "取关条件"],
        "trigger_terms": ["候选质量", "动作上限", "恢复条件", "取关条件", "风险项"],
        "scenarios": ["daily_report", "candidate_quality", "review"],
        "report_slot": "候选质量",
        "confidence": "verified",
        "impact": "候选先看质量、风险和动作上限；旧分数只作兼容字段，最多能做什么由条件链决定。",
    },
    {
        "id": "principle.anti-fake-precision",
        "prior": "first-principles-prior",
        "source_path": "wiki/交易思想/反伪精确第一性原理.md",
        "title": "反伪精确第一性原理",
        "topics": ["第一性原理", "反伪精确", "条件链", "价格行为", "淘汰赛", "板块资金扩散", "资金载体"],
        "trigger_terms": [
            "第一性原理",
            "伪精确",
            "评分",
            "分数",
            "加权",
            "指标",
            "成功率",
            "概率",
            "淘汰赛",
            "条件链",
            "布鲁克斯",
            "板块资金扩散",
            "资金载体",
            "量化参与痕迹",
            "趋势容量核心",
            "板块锚",
            "中军",
            "分支龙头",
        ],
        "scenarios": ["daily_report", "intraday_question", "candidate_quality", "review"],
        "report_slot": "选股原则",
        "confidence": "verified",
        "impact": "事实数值保留，主观判断不能写成精确分；日报先从市场资金结构和板块资金扩散找资金载体，再按角色、量化参与痕迹、反证、价格行为和账户条件逐层收口。",
    },
    {
        "id": "market.new-stock-cycle-boundary",
        "prior": "market-structure-prior",
        "source_path": "wiki/交易思想/新股周期与市场情绪.md",
        "title": "新股周期不能替代单票承接",
        "topics": ["新股周期", "市场情绪", "承接验证"],
        "trigger_terms": ["新股", "次新", "情绪出口", "弱修复", "强修复"],
        "scenarios": ["daily_report", "review"],
        "report_slot": "市场结构判断",
        "confidence": "verified",
        "impact": "新股情绪只作为周期和承接判断，仍要回到单票承接验证。",
    },
    {
        "id": "knowledge.replay-five-fields",
        "prior": "knowledge-compounding-prior",
        "source_path": "wiki/交易思想/AI摩擦与知识复利.md",
        "title": "复盘沉淀五字段",
        "topics": ["知识复利", "复盘", "判断样本"],
        "trigger_terms": ["复盘", "错题", "当时判断", "实际偏差", "可复用规则"],
        "scenarios": ["review", "daily_report", "intraday_question"],
        "report_slot": "知识复利提示",
        "confidence": "reviewed",
        "impact": "复盘按价格事实、当时判断、实际偏差、可复用规则、下次动作沉淀。",
    },
    {
        "id": "market.price-volume-contradiction",
        "prior": "market-structure-prior",
        "source_path": "wiki/交易思想/价格行为与能量框架.md",
        "title": "指数价跌量增先防踩踏",
        "topics": ["价格行为", "成交量", "指数价跌量增"],
        "trigger_terms": ["指数大跌", "放量", "价跌量增", "踩踏", "出货风险"],
        "scenarios": ["daily_report", "review"],
        "report_slot": "市场结构判断",
        "confidence": "verified",
        "impact": "指数或全市场大跌且成交放大时，优先按卖压释放、量化踩踏或出货风险处理。",
    },
    {
        "id": "price-action.brooks-trend-framework",
        "prior": "price-action-prior",
        "source_path": "wiki/交易思想/布鲁克斯价格行为趋势.md",
        "title": "布鲁克斯价格行为趋势框架",
        "topics": ["价格行为", "价格趋势优先", "A股量价本地化", "叙事后置", "趋势区间谱系", "始终入场", "二次入场", "交易者等式"],
        "trigger_terms": [
            "布鲁克斯",
            "价格行为",
            "价格趋势",
            "叙事后置",
            "按图索因",
            "按因索图",
            "基本面",
            "找原因",
            "量价",
            "成交量",
            "放量",
            "缩量",
            "资金表态",
            "指标组合",
            "趋势区间",
            "始终入场",
            "二次入场",
            "信号K线",
            "急速与通道",
            "交易者等式",
            "假底",
            "进攻雏形",
            "再等等",
            "重心上移",
            "缩量横盘",
            "前高",
            "利空不深跌",
            "利好不大涨",
            "阳包阴",
            "突破阳线",
        ],
        "scenarios": ["daily_report", "intraday_question", "candidate_quality", "review"],
        "report_slot": "价格行为判断",
        "confidence": "reviewed",
        "impact": "先判趋势/交易区间，再看信号是否有后续行情；成交量只作资金表态证据，必须由价格强收盘、回踩不破或后续行情确认；错过强趋势只允许小仓按同一失效线参与。",
    },
    {
        "id": "price-action.entry-quality-three-conditions",
        "prior": "entry-quality-prior",
        "source_path": "wiki/交易思想/价格行为与能量框架.md",
        "title": "追涨杀跌动作中性与买点三条件",
        "topics": ["追涨杀跌", "买点质量", "趋势地基", "盈亏同源点", "股性过滤", "异动K线"],
        "trigger_terms": [
            "追涨杀跌",
            "追涨",
            "杀跌",
            "买点",
            "趋势地基",
            "地基",
            "盈亏同源",
            "股性",
            "异动K线",
            "异动K",
            "旱地拔葱",
            "反包",
        ],
        "scenarios": ["daily_report", "intraday_question", "candidate_quality", "review"],
        "report_slot": "买点质量",
        "confidence": "reviewed",
        "impact": "追涨杀跌只是动作，先验趋势地基、盈亏同源点和股性；无地基急拉只观察，贴近认错线且次日重新承接后才进入参与评估。",
    },
    {
        "id": "discipline.present-execution",
        "prior": "trade-discipline-prior",
        "source_path": "wiki/交易思想/价格行为与能量框架.md",
        "title": "当下执行与心理时间校准",
        "topics": ["当下执行", "心理时间", "短线当下性", "未来焦虑"],
        "trigger_terms": [
            "当下",
            "焦虑",
            "焦躁",
            "未来",
            "短线",
            "价值投资",
            "新股",
            "暴涨",
            "预测",
            "期待",
        ],
        "scenarios": ["daily_report", "intraday_question", "review"],
        "report_slot": "交易纪律",
        "confidence": "reviewed",
        "impact": "计划和复盘可以面向未来，但盘中执行只看当下价格、承接、窗口和失效线；远期价值、新股暴涨想象和题材后续发酵只进观察或研究。",
    },
    {
        "id": "market.logic-chain-expansion",
        "prior": "market-structure-prior",
        "source_path": "wiki/板块补充/板块中枢与主线延续.md",
        "title": "炒作逻辑链扩散后再升级",
        "topics": ["主线延续", "炒作逻辑链", "板块扩散"],
        "trigger_terms": ["逻辑链", "上游", "中游", "下游", "扩散", "主线延续"],
        "scenarios": ["daily_report", "review"],
        "report_slot": "市场结构判断",
        "confidence": "verified",
        "impact": "同一炒作逻辑链连续扩散并有后排承接时，才提高修复级别。",
    },
    {
        "id": "market.rebound-quality-active-passive",
        "prior": "market-structure-prior",
        "source_path": "wiki/板块补充/板块中枢与主线延续.md",
        "title": "板块反弹质量与主动被动分层",
        "topics": ["反弹质量", "板块指数", "主动做多", "主动带动反弹", "跟随指数反弹", "熟悉资产修复", "节奏共振待确认", "冰点接冰点", "值博率"],
        "trigger_terms": [
            "反弹质量",
            "板块指数",
            "指数走坏",
            "板块走坏",
            "主动做多",
            "主动反弹",
            "主动带动",
            "带动市场",
            "领涨",
            "资金主动",
            "被动带下去",
            "被动下跌",
            "跟随反弹",
            "跟随指数",
            "减亏离场",
            "降风险窗口",
            "熟悉资产修复",
            "调研充分",
            "未来预期良好",
            "持续承接",
            "深V",
            "国产链",
            "先于指数",
            "节奏不匹配",
            "共振待确认",
            "冰点接冰点",
            "值博率",
            "弹簧",
        ],
        "fact_conditions": {
            "must_any": [
                {"path": "market.rebound_roles", "contains_any": ["主动带动反弹"], "label": "主动带动反弹"},
                {"path": "market.rebound_roles", "contains_any": ["跟随指数反弹"], "label": "跟随指数反弹"},
                {"path": "market.rebound_roles", "contains_any": ["熟悉资产修复"], "label": "熟悉资产修复"},
                {"path": "market.rebound_state", "contains_any": ["节奏共振待确认"], "label": "节奏共振待确认"},
                {"path": "market.rebound_action", "contains_any": ["减风险", "减亏离场", "B1参与权"], "label": "反弹动作分类"},
                {"path": "candidate.rebound_roles", "contains_any": ["主动带动反弹"], "label": "主动带动反弹"},
                {"path": "candidate.rebound_roles", "contains_any": ["跟随指数反弹"], "label": "跟随指数反弹"},
                {"path": "candidate.rebound_roles", "contains_any": ["熟悉资产修复"], "label": "熟悉资产修复"},
                {"path": "candidate.rebound_action", "contains_any": ["减风险", "减亏离场", "B1参与权"], "label": "反弹动作分类"},
                {"path": "position.rebound_roles", "contains_any": ["跟随指数反弹", "熟悉资产修复"], "label": "持仓反弹分类"},
                {"path": "position.rebound_action", "contains_any": ["减风险", "减亏离场", "持续承接确认"], "label": "持仓动作分类"},
            ],
            "prefer_any": [
                {"path": "market.rebound_state", "contains_any": ["指数深V"], "label": "指数深V"},
                {"path": "market.rebound_state", "contains_any": ["先于指数"], "label": "先于指数"},
                {"path": "market.rebound_state", "contains_any": ["板块高潮"], "label": "板块高潮"},
                {"path": "candidate.rebound_state", "contains_any": ["先于指数"], "label": "先于指数"},
                {"path": "candidate.rebound_state", "contains_any": ["板块高潮"], "label": "板块高潮"},
            ],
        },
        "scenarios": ["daily_report", "intraday_question", "candidate_quality", "review"],
        "report_slot": "市场结构判断",
        "confidence": "reviewed",
        "impact": "反弹先分类再写动作：主动带动反弹按进攻线观察，可给B1参与权并等待B2确认；跟随指数反弹优先按减亏离场或降风险窗口；熟悉资产修复看持续承接和板块逻辑共振。板块先于指数上涨后遇到指数深V，只写共振待确认，次日看分歧承接、扩散延续和风险偏好是否被真正带动。",
    },
    {
        "id": "market.early-belief-fish-body-cycle",
        "prior": "market-structure-prior",
        "source_path": "wiki/板块补充/板块中枢与主线延续.md",
        "title": "早信不是早买，鱼身只吃中段",
        "topics": ["早信", "鱼身", "无人问津", "人声鼎沸", "龙头二次发力", "后手风险"],
        "trigger_terms": [
            "早信",
            "鱼身",
            "鱼头",
            "鱼尾",
            "无人问津",
            "人声鼎沸",
            "龙头二次发力",
            "二次发力",
            "主动卖飞",
            "终于想通",
            "后手追涨",
        ],
        "scenarios": ["daily_report", "intraday_question", "candidate_quality", "review"],
        "report_slot": "市场结构判断",
        "confidence": "reviewed",
        "impact": "早信只提高观察优先级，不替代买入资格；龙头或分支二次发力后，再看固定交易窗口、板块同步、个股承接和亏损边界。鱼身只吃信号确认后到人声鼎沸前的中段，先涨者转弱、补涨扩散或权重拉指数时主动降风险。",
    },
    {
        "id": "research.supply-chain-bottleneck",
        "prior": "research-framework-prior",
        "source_path": "wiki/板块补充/供应链瓶颈研究法.md",
        "title": "供应链瓶颈先研究后交易",
        "topics": ["供应链瓶颈", "产业链拆解", "关键材料", "不可替代", "反方验证"],
        "trigger_terms": [
            "供应链瓶颈",
            "产业链瓶颈",
            "关键瓶颈",
            "不可替代",
            "CPO瓶颈",
            "CPO供应链",
            "光通信瓶颈",
            "InP",
            "衬底",
            "关键材料",
            "产能稀缺",
            "客户认证",
            "反方验证",
        ],
        "scenarios": ["daily_report", "intraday_question", "candidate_quality", "review"],
        "report_slot": "研究线索",
        "confidence": "reviewed",
        "impact": "先拆产业链并验证瓶颈，再把线索降维成研究优先级；不直接生成买入资格，交易动作仍看价格承接、板块选择和失效条件。",
    },
]


def _flatten_terms(value: Any) -> List[str]:
    terms: List[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            terms.append(str(key))
            terms.extend(_flatten_terms(item))
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            terms.extend(_flatten_terms(item))
    elif value is not None:
        text = str(value).strip()
        if text:
            terms.append(text)
    return terms


def _joined_terms(facts: Dict[str, Any]) -> str:
    terms = _flatten_terms(facts or {})
    market = (facts or {}).get("market") if isinstance(facts, dict) else {}
    if isinstance(market, dict) and str(market.get("index_trend", "") or "").strip() == "上涨":
        terms.append("指数上涨")
    return " ".join(terms)


def _value_at_path(value: Any, path: str) -> Any:
    current = value
    for part in str(path or "").split("."):
        if not part:
            continue
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _condition_matches(facts: Dict[str, Any], condition: Dict[str, Any]) -> bool:
    values = _flatten_terms(_value_at_path(facts, str(condition.get("path") or "")))
    if not values:
        return False
    haystack = " ".join(values)
    if condition.get("exists"):
        return True
    if "equals" in condition:
        expected = str(condition.get("equals") or "").strip()
        return any(value == expected for value in values)
    if "contains" in condition:
        expected = str(condition.get("contains") or "").strip()
        return bool(expected and expected in haystack)
    expected_values = [str(item or "").strip() for item in condition.get("contains_any") or []]
    return any(expected and expected in haystack for expected in expected_values)


def _matched_fact_conditions(entry: Dict[str, Any], facts: Dict[str, Any]) -> List[str]:
    conditions = entry.get("fact_conditions") if isinstance(entry.get("fact_conditions"), dict) else {}
    matched_by_group: Dict[str, List[str]] = {"must_any": [], "prefer_any": []}
    for group in matched_by_group:
        for condition in conditions.get(group) or []:
            if not isinstance(condition, dict) or not _condition_matches(facts, condition):
                continue
            label = str(condition.get("label") or condition.get("path") or "").strip()
            if label:
                matched_by_group[group].append(label)
    if conditions.get("must_any") and not matched_by_group["must_any"]:
        return []
    matched = [*matched_by_group["must_any"], *matched_by_group["prefer_any"]]
    return list(dict.fromkeys(matched))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value not in (None, ""):
            return float(value)
    except (TypeError, ValueError):
        return default
    return default


def _first_dict(*values: Any) -> Dict[str, Any]:
    for value in values:
        if isinstance(value, dict):
            return value
    return {}


def _build_market_fact_tags(data: Dict[str, Any]) -> Dict[str, Any]:
    judgement = _first_dict(data.get("market_structure_judgement"))
    summary_text = str(judgement.get("summary_text") or "")
    fact_basis_text = " ".join(str(item or "") for item in judgement.get("fact_basis") or [])
    index_relation = str(judgement.get("index_profit_relation") or "")
    combined_text = " ".join([summary_text, fact_basis_text, index_relation])
    market_facts: Dict[str, Any] = {}
    if "指数强" in index_relation or "指数强" in summary_text:
        market_facts["index_trend"] = "上涨"
    if "上涨家数偏弱" in fact_basis_text or "真实赚钱效应弱" in summary_text:
        market_facts["breadth"] = "上涨家数偏弱"
    if "结构集中" in summary_text:
        market_facts["turnover_distribution"] = "成交集中"
    if "结构性行情" in combined_text:
        market_facts["market_form"] = "结构性行情"
    if "九宫格" in combined_text or "网格化" in combined_text or "板块格子" in combined_text:
        market_facts["sector_grid"] = "水池九宫格"
    if "先选板块" in combined_text or "板块先行" in combined_text:
        market_facts["selection_order"] = "先选板块"
    if "边角" in combined_text:
        market_facts["corner_sample"] = "边角标的"
    _merge_rebound_facts(market_facts, _rebound_facts_from_text(combined_text))
    return market_facts


def _rebound_facts_from_text(text: str) -> Dict[str, List[str]]:
    rebound_roles: List[str] = []
    rebound_state: List[str] = []
    rebound_action: List[str] = []
    if any(term in text for term in ["主动带动", "主动反弹", "主动做多", "带动市场", "领涨"]):
        rebound_roles.append("主动带动反弹")
        rebound_action.append("B1参与权")
    if any(term in text for term in ["跟随反弹", "跟随指数", "被动跟涨", "被动反弹"]):
        rebound_roles.append("跟随指数反弹")
        rebound_action.extend(["减亏离场", "减风险"])
    if any(term in text for term in ["熟悉资产修复", "调研充分", "未来预期良好", "不愿意追陌生领涨", "持续承接"]):
        rebound_roles.append("熟悉资产修复")
        rebound_action.append("持续承接确认")
    if "深V" in text:
        rebound_state.append("指数深V")
    if "先于指数" in text:
        rebound_state.append("先于指数")
    if "板块高潮" in text:
        rebound_state.append("板块高潮")
    if any(term in text for term in ["节奏不匹配", "共振待确认", "共振是否有效也并未确认"]):
        rebound_state.append("节奏共振待确认")
    rebound_facts: Dict[str, List[str]] = {}
    if rebound_roles:
        rebound_facts["rebound_roles"] = list(dict.fromkeys(rebound_roles))
    if rebound_state:
        rebound_facts["rebound_state"] = list(dict.fromkeys(rebound_state))
    if rebound_action:
        rebound_facts["rebound_action"] = list(dict.fromkeys(rebound_action))
    return rebound_facts


def _merge_rebound_facts(target: Dict[str, Any], rebound_facts: Dict[str, List[str]]) -> None:
    for key in ("rebound_roles", "rebound_state", "rebound_action"):
        values = rebound_facts.get(key) or []
        if not values:
            continue
        existing = target.get(key) if isinstance(target.get(key), list) else []
        target[key] = list(dict.fromkeys([*existing, *values]))


def _candidate_from_data(data: Dict[str, Any]) -> Dict[str, Any]:
    return _first_dict(
        data.get("selected_position_candidate"),
        data.get("selected_candidate"),
        data.get("watch_anchor"),
        _first_dict(data.get("market_research_snapshot")).get("selected_position_candidate"),
    )


def _account_from_data(data: Dict[str, Any]) -> Dict[str, Any]:
    personal_position_context = _first_dict(data.get("personal_position_context"))
    market_research_snapshot = _first_dict(data.get("market_research_snapshot"))
    return _first_dict(
        data.get("account_profile"),
        data.get("account"),
        personal_position_context.get("account_profile"),
        market_research_snapshot.get("account_profile"),
    )


def _final_target_resolution_from_data(data: Dict[str, Any]) -> Dict[str, Any]:
    market_research_snapshot = _first_dict(data.get("market_research_snapshot"))
    execution_stage_context = _first_dict(data.get("execution_stage_context"))
    return _first_dict(
        data.get("final_target_resolution"),
        execution_stage_context.get("final_target_resolution"),
        market_research_snapshot.get("final_target_resolution"),
    )


def _existing_position_summary_from_data(data: Dict[str, Any]) -> Dict[str, Any]:
    personal_position_context = _first_dict(data.get("personal_position_context"))
    market_research_snapshot = _first_dict(data.get("market_research_snapshot"))
    return _first_dict(
        data.get("existing_position_summary"),
        personal_position_context.get("existing_position_summary"),
        market_research_snapshot.get("existing_position_summary"),
    )


def _has_existing_position(position: Dict[str, Any]) -> bool:
    if not isinstance(position, dict) or not position:
        return False
    if position.get("has_position") is False:
        return False
    if position.get("position_count") == 0:
        return False
    identity_keys = ("name", "stock_name", "code", "stock_code", "symbol")
    if any(str(position.get(key) or "").strip() for key in identity_keys):
        return True
    return bool(position.get("has_position"))


def _build_account_candidate_fact_tags(data: Dict[str, Any]) -> Dict[str, Any]:
    account = _account_from_data(data)
    candidate = _candidate_from_data(data)
    account_facts: Dict[str, Any] = {}
    candidate_facts: Dict[str, Any] = {}

    cash_available = _safe_float(account.get("cash_available"), default=0.0)
    one_lot_amount = _safe_float(candidate.get("one_lot_amount"), default=0.0)
    if cash_available:
        account_facts["cash_available"] = cash_available
    if one_lot_amount:
        candidate_facts["one_lot_amount"] = one_lot_amount
    if cash_available and one_lot_amount and one_lot_amount > cash_available:
        account_facts["status"] = "实际不可买"

    identity = str(candidate.get("identity") or candidate.get("cycle_identity") or candidate.get("market_identity") or "").strip()
    if identity:
        candidate_facts["identity"] = identity

    quality_terms = []
    if candidate.get("action_limit") or candidate.get("action_cap"):
        quality_terms.append("动作上限")
    if candidate.get("risk_items") or candidate.get("risk_flags"):
        quality_terms.append("风险项")
    if candidate.get("recover_condition") or candidate.get("recovery_condition"):
        quality_terms.append("恢复条件")
    if candidate.get("drop_condition") or candidate.get("remove_condition"):
        quality_terms.append("取关条件")
    if quality_terms:
        candidate_facts["quality"] = ["候选质量", *quality_terms]
    _merge_rebound_facts(candidate_facts, _rebound_facts_from_text(" ".join(_flatten_terms(candidate))))

    return {"account": account_facts, "candidate": candidate_facts}


def _build_position_capital_fact_tags(data: Dict[str, Any]) -> Dict[str, Any]:
    resolution = _final_target_resolution_from_data(data)
    decision = _first_dict(resolution.get("capital_priority_decision"))
    existing_position = _first_dict(
        resolution.get("existing_position_target"),
        _existing_position_summary_from_data(data),
    )
    exposure_plan = _first_dict(resolution.get("account_exposure_plan"))
    new_entry = _first_dict(
        resolution.get("new_entry_target"),
        resolution.get("tradable_proxy_target"),
        resolution.get("watch_target"),
    )

    position_facts: Dict[str, Any] = {}
    candidate_facts: Dict[str, Any] = {}
    capital_priority = str(decision.get("capital_priority") or "").strip()
    reason = str(decision.get("reason") or "").strip()
    old_position_priority = {
        "old_position_t",
        "old_position",
        "existing_position",
        "existing_position_t",
        "new_entry_after_old_exit",
    }
    switch_priority = {"new_entry_after_old_exit"}
    new_entry_priority = {"new_entry", "tradable_proxy"}
    has_existing_position = _has_existing_position(existing_position)
    same_stock_t = bool(exposure_plan.get("same_stock_t") or capital_priority == "same_stock_t")

    if has_existing_position or capital_priority in old_position_priority or same_stock_t:
        position_facts["state"] = "旧仓"
    if same_stock_t:
        position_facts["action"] = "同股T"
        candidate_facts.setdefault("quality", []).extend(["同股T", "临时2x"])
    if capital_priority in switch_priority:
        position_facts["action"] = "换仓"
        candidate_facts.setdefault("quality", []).append("新机会")
    elif new_entry and has_existing_position and capital_priority in new_entry_priority:
        candidate_facts.setdefault("quality", []).append("新机会")
    if new_entry and capital_priority in switch_priority:
        candidate_facts.setdefault("quality", []).append("换仓")
    if "满仓" in reason:
        candidate_facts.setdefault("quality", []).append("满仓")
    if reason and position_facts:
        position_facts["capital_priority_reason"] = reason
    if capital_priority and position_facts:
        position_facts["capital_priority"] = capital_priority
    _merge_rebound_facts(candidate_facts, _rebound_facts_from_text(" ".join(_flatten_terms(new_entry))))
    if has_existing_position:
        _merge_rebound_facts(position_facts, _rebound_facts_from_text(" ".join(_flatten_terms([existing_position, reason]))))

    result: Dict[str, Any] = {}
    if position_facts:
        result["position"] = position_facts
    if candidate_facts:
        result["candidate"] = candidate_facts
    if capital_priority:
        result["capital_priority"] = capital_priority
    return result


def _build_decision_response_fact_tags(data: Dict[str, Any]) -> Dict[str, Any]:
    resolution = _final_target_resolution_from_data(data)
    final = _first_dict(resolution.get("final"), resolution.get("final_action"))
    planned_participation = _first_dict(
        resolution.get("planned_participation"),
        resolution.get("participation_script"),
        final.get("planned_participation"),
        final.get("participation_script"),
    )
    target = _first_dict(
        final.get("execution_object"),
        final.get("target"),
        resolution.get("execution_object"),
        resolution.get("new_entry_target"),
        resolution.get("display_target"),
        resolution.get("watch_target"),
    )
    position_pct = final.get("position_pct", resolution.get("position_pct"))
    text_parts = _flatten_terms(
        [
            final.get("label"),
            final.get("action_text"),
            final.get("action"),
            final.get("reason"),
            final.get("failure_conditions"),
            resolution.get("action_text"),
            resolution.get("tomorrow_action"),
            resolution.get("reason"),
            resolution.get("failure_conditions"),
            resolution.get("participation_script"),
            planned_participation.get("confirm_conditions"),
            planned_participation.get("cancellation_conditions"),
            planned_participation.get("entry_plan"),
            planned_participation.get("risk_plan"),
            planned_participation.get("position_plan"),
        ]
    )
    combined = " ".join(text_parts)
    tags: List[str] = []
    structured: Dict[str, Any] = {}

    try:
        numeric_position = int(float(position_pct))
    except (TypeError, ValueError):
        numeric_position = None
    if numeric_position == 0:
        tags.append("0%不参与")
        structured["position_plan"] = "0%不参与"
    if not target and ("0%不参与" in combined or "不参与" in combined or "只观察" in combined):
        tags.append("无执行目标")
        structured["execution_object_state"] = "无执行目标"
    for term in [
        "0%不参与",
        "只观察",
        "无执行目标",
        "第一动作",
        "B1",
        "B2",
        "B1参与权",
        "B2确认权",
        "踏空焦虑",
        "买入资格",
        "不强行凑个股",
        "应对剧本",
    ]:
        if term in combined:
            tags.append(term)
    if "只观察" in combined:
        structured["action_layer"] = "只观察"
    if "第一动作" in combined:
        structured["participation_rhythm"] = "第一动作"
    if "B1" in combined:
        structured["b1_role"] = "参与权"
    if "B2" in combined:
        structured["b2_role"] = "确认权"
    if "买入资格" in combined:
        structured["qualification"] = "买入资格"
    if "应对剧本" in combined:
        structured["response_mode"] = "应对剧本"
    behavior_traps = [
        term
        for term in ["踏空焦虑", "阳线追后排", "回本卖出", "小赚止盈"]
        if term in combined
    ]
    if behavior_traps:
        structured["behavior_traps"] = behavior_traps

    unique_tags = list(dict.fromkeys(tags))
    if not unique_tags and not structured:
        return {}
    response_facts: Dict[str, Any] = dict(structured)
    if unique_tags:
        response_facts["response_script"] = unique_tags
    return {"decision": response_facts}


def build_llm_wiki_fact_tags(data: Dict[str, Any] | None) -> Dict[str, Any]:
    """Extract compact fact tags used by the explainable Wiki router."""
    if not isinstance(data, dict):
        return {}
    explicit = data.get("knowledge_hit_facts")
    if isinstance(explicit, dict):
        return dict(explicit)

    facts: Dict[str, Any] = {}
    market_facts = _build_market_fact_tags(data)
    if market_facts:
        facts["market"] = market_facts
    account_candidate = _build_account_candidate_fact_tags(data)
    for key, value in account_candidate.items():
        if value:
            facts[key] = value
    position_capital = _build_position_capital_fact_tags(data)
    for key, value in position_capital.items():
        if not value:
            continue
        if isinstance(value, dict) and isinstance(facts.get(key), dict):
            merged = dict(facts[key])
            for nested_key, nested_value in value.items():
                if isinstance(nested_value, list) and isinstance(merged.get(nested_key), list):
                    merged[nested_key] = list(dict.fromkeys([*merged[nested_key], *nested_value]))
                else:
                    merged[nested_key] = nested_value
            facts[key] = merged
        else:
            facts[key] = value
    decision_response = _build_decision_response_fact_tags(data)
    for key, value in decision_response.items():
        if not value:
            continue
        if isinstance(value, dict) and isinstance(facts.get(key), dict):
            merged = dict(facts[key])
            for nested_key, nested_value in value.items():
                if isinstance(nested_value, list) and isinstance(merged.get(nested_key), list):
                    merged[nested_key] = list(dict.fromkeys([*merged[nested_key], *nested_value]))
                else:
                    merged[nested_key] = nested_value
            facts[key] = merged
        else:
            facts[key] = value
    return facts


def _term_matches(term: str, text: str) -> bool:
    return bool(term and term in text)


def _matched_trigger_terms(entry: Dict[str, Any], facts_text: str) -> List[str]:
    return [
        str(term)
        for term in entry.get("trigger_terms", [])
        if _term_matches(str(term), facts_text)
    ]


def _entry_requirements_satisfied(entry: Dict[str, Any], matched_terms: List[str], matched_conditions: List[str]) -> bool:
    weak_terms = {str(term) for term in entry.get("weak_trigger_terms", [])}
    if weak_terms and matched_terms and not matched_conditions and all(term in weak_terms for term in matched_terms):
        return False
    return True


def _scenario_allowed(entry: Dict[str, Any], scenario: str) -> bool:
    scenarios = [str(item) for item in entry.get("scenarios", [])]
    return not scenario or scenario in scenarios


def _build_hit(entry: Dict[str, Any], matched_terms: Iterable[str], matched_conditions: Iterable[str], index: int) -> Dict[str, Any]:
    triggered_by = list(dict.fromkeys([*list(matched_terms), *list(matched_conditions)]))
    return {
        "hit_id": f"kh-{index:03d}",
        "knowledge_id": entry["id"],
        "prior": entry["prior"],
        "source_path": entry["source_path"],
        "title": entry["title"],
        "triggered_by": triggered_by,
        "matched_conditions": list(matched_conditions),
        "matched_topics": list(entry.get("topics", [])),
        "impact": entry["impact"],
        "report_slot": entry["report_slot"],
        "confidence": entry["confidence"],
    }


def route_llm_wiki_knowledge(
    facts: Dict[str, Any] | None,
    *,
    scenario: str = "daily_report",
    limit: int = 3,
) -> List[Dict[str, Any]]:
    """Return explainable Wiki knowledge hits for the supplied report facts."""
    facts_text = _joined_terms(facts or {})
    ranked_matches = []
    for order, entry in enumerate(KNOWLEDGE_INDEX):
        if not _scenario_allowed(entry, scenario):
            continue
        matched_terms = _matched_trigger_terms(entry, facts_text)
        matched_conditions = _matched_fact_conditions(entry, facts or {})
        if (matched_terms or matched_conditions) and _entry_requirements_satisfied(entry, matched_terms, matched_conditions):
            score = len(matched_terms) + len(matched_conditions) * 2
            ranked_matches.append((score, len(matched_conditions), len(matched_terms), -order, entry, matched_terms, matched_conditions))

    ranked_matches.sort(reverse=True)
    hits = []
    for _, _, _, _, entry, matched_terms, matched_conditions in ranked_matches[: max(0, int(limit or 0))]:
        hits.append(_build_hit(entry, matched_terms, matched_conditions, len(hits) + 1))
    return hits


__all__ = ["KNOWLEDGE_INDEX", "build_llm_wiki_fact_tags", "route_llm_wiki_knowledge"]
