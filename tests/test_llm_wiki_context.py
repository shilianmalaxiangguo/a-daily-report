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

        self.assertEqual(context["version"], "2026-05-18")
        self.assertEqual(context["source"], "llm_wiki")
        self.assertEqual(context["language"], "zh-CN")
        self.assertIn("wiki/交易思想/缠论体系.md", context["source_paths"])
        self.assertIn("wiki/交易思想/价格行为与能量框架.md", context["source_paths"])
        self.assertIn("wiki/交易思想/启动板与趋势持股短板.md", context["source_paths"])
        self.assertIn("wiki/交易思想/极度看好参与时机.md", context["source_paths"])
        self.assertIn("wiki/交易思想/交易错题本.md", context["source_paths"])
        self.assertIn("wiki/交易思想/新股周期与市场情绪.md", context["source_paths"])
        self.assertIn("wiki/板块补充/板块中枢与主线延续.md", context["source_paths"])
        self.assertIn("wiki/交易思想/日报术语契约.md", context["source_paths"])
        self.assertIn("wiki/运行契约/日报数据源契约.md", context["source_paths"])
        self.assertIn("wiki/运行契约/snap-ui发布契约.md", context["source_paths"])
        self.assertIn("日线结构中枢定环境 -> 参与窗口分层确认 -> 30分钟止损", context["field_mappings"])
        self.assertIn("普通结构确认 -> 60分钟确认；强核心快路径 -> 竞价表态、开盘前几分钟或回封", context["field_mappings"])
        self.assertIn("参与时机 -> open_core开盘核心 / ten_confirm 10点确认 / tail_exception尾盘例外 / no_trade不交易", context["field_mappings"])
        self.assertIn("统一来源 -> 日报写入decision-ledger planned_participation，snap-ui只消费不重算", context["field_mappings"])
        self.assertIn("极度看好复盘 -> 日报生成时用行情表回写participation_review，封死买不到不算收益命中", context["field_mappings"])
        self.assertIn("价格裁判 -> 资金流/指标只作辅助，价格站回强弱线才升级资格", context["field_mappings"])
        self.assertIn("该涨不涨 -> 时间消耗风险，降级/减仓/换样本", context["field_mappings"])
        self.assertIn("生存优先 -> 小资金T+1先控制满仓隔夜风险", context["field_mappings"])
        self.assertIn("数学期望 -> 低回撤和稳定复利优先于单日大盈利次数", context["field_mappings"])
        self.assertIn("攻击频次 -> 没有防守边界的高频进攻会把收益对冲成无效波动", context["field_mappings"])
        self.assertIn("亏损边界 -> 先避免大亏损，再追求偶尔向上大盈利", context["field_mappings"])
        self.assertIn("胜率赔率 -> 胜率接近天花板时用大赚小亏和利润奔跑修复期望", context["field_mappings"])
        self.assertIn("赚钱效应退潮 -> 单边趋势道寻常，震荡退潮期降低攻击频次和预期收益", context["field_mappings"])
        self.assertIn("集中大赚 -> 必须先写代价和平衡，不能把追求大赚变成无边界押注", context["field_mappings"])
        self.assertIn("板块节奏 -> 量化环境下先看板块路径和资金选择，再看单一龙头定价", context["field_mappings"])
        self.assertIn("资金阶段 -> 小资金允许追求高弹性，但只做市场承认的热门核心，不做随机高波动", context["field_mappings"])
        self.assertIn("热门妖股 -> 价格、成交、辨识度、板块地位共同确认的核心，不是听来的故事票", context["field_mappings"])
        self.assertIn("辨识度优先 -> 高弹性交易优先选择市场共识最强的核心标的，宁可少做不做边缘票", context["field_mappings"])
        self.assertIn("新股辨识度 -> 新股身份不是辨识度，只有盟固利/无线传媒式情绪旗帜才升级为核心", context["field_mappings"])
        self.assertIn("趋势容错 -> 上升趋势/短期周期未破时容错高，下降趋势/周期破坏时容错低", context["field_mappings"])
        self.assertIn("周期持有 -> 短线按博弈周期判断，周期未破可持有，周期破坏先退出", context["field_mappings"])
        self.assertIn("启动板 -> 短线触发转趋势观察仓，必须记录启动逻辑、持股规则、破坏退出", context["field_mappings"])
        self.assertIn("趋势持股短板 -> 卖出原因可复盘，区分风险信号和情绪信号", context["field_mappings"])
        self.assertIn("换仓错题 -> 先证明旧仓失效，再证明新仓更强，最后证明新仓风险能承受", context["field_mappings"])
        self.assertIn("亏损后切换 -> 当天默认暂停新方向，禁止用更高波动标的找回本金", context["field_mappings"])
        self.assertIn("明日交易计划 -> 账户状态、持仓处理、时间窗口、大盘剧本、板块锚点、候选预演、禁止清单", context["field_mappings"])
        self.assertIn("无计划新方向 -> 未写入前一晚计划且未通过四重确认，盘中默认没有满仓买入资格", context["field_mappings"])
        self.assertIn("禁止清单 -> 不该做什么优先级高于想买什么，先拦错再谈进攻", context["field_mappings"])
        self.assertIn("来源保真 -> 区分原文可支持、系统化抽象、不能归因给原文", context["field_mappings"])
        self.assertIn("新股周期 -> 市场周期、新股扩散、首日情绪、C阶段承接、情绪出口地位", context["field_mappings"])
        self.assertIn("新股样本 -> 盟固利是弱市投机宣泄；无线传媒是强修复情绪出口；历史相似不能替代当前承接验证", context["field_mappings"])
        self.assertIn("稳定知识写入 LLM Wiki", context["write_boundaries"])
        self.assertIn("原文不直接进入日报主链", context["report_boundaries"])
        self.assertIn("MACD只能作为辅助", context["report_boundaries"])
        self.assertIn("用户可见输出不用旧工程口径，改用资格/条件/可做/参与/不参与", context["report_boundaries"])
        self.assertIn("fresh daily generation uses Tushare-first", context["data_source_policy"])
        self.assertIn("akshare/iwencai are fallback only", context["data_source_policy"])
        self.assertIn("snap-ui publish verifies Cloudflare module assets before push", context["publish_policy"])
        self.assertIn("develop is the Cloudflare Pages branch", context["publish_policy"])

    def test_build_llm_wiki_context_keeps_report_digest_short_and_fieldized(self):
        context = build_llm_wiki_context()
        digest = context["report_digest_text"]

        self.assertIn("角度与幅度", digest)
        self.assertIn("价格是裁判", digest)
        self.assertIn("资金流和指标只作辅助", digest)
        self.assertIn("该涨不涨按时间消耗风险降级", digest)
        self.assertIn("低回撤和稳定复利优先", digest)
        self.assertIn("攻击频次服从亏损边界", digest)
        self.assertIn("先避免大亏再追求大赚", digest)
        self.assertIn("胜率难绝对统治时靠赔率", digest)
        self.assertIn("集中追求大赚先写代价和平衡", digest)
        self.assertIn("板块节奏优先", digest)
        self.assertIn("单一龙头定价权降低", digest)
        self.assertIn("小资金可追高弹性但只做市场承认的热门核心", digest)
        self.assertIn("辨识度优先", digest)
        self.assertIn("新股身份不是辨识度", digest)
        self.assertIn("新股先判市场周期和扩散", digest)
        self.assertIn("趋势容错看周期是否未破", digest)
        self.assertIn("周期破坏先退出", digest)
        self.assertIn("启动板只给趋势观察仓资格", digest)
        self.assertIn("换仓先证旧仓失效、新仓更强、风险能承受", digest)
        self.assertIn("亏损后不切更高波动新方向", digest)
        self.assertIn("前夜计划先定账户状态和禁止清单", digest)
        self.assertIn("无计划新方向盘中无满仓资格", digest)
        self.assertIn("趋势卖出必须可复盘", digest)
        self.assertIn("不把系统化抽象冒充原文", digest)
        self.assertIn("C阶段承接", digest)
        self.assertIn("不用历史妖股相似替代当前验证", digest)
        self.assertIn("参与窗口分层确认", digest)
        self.assertIn("普通结构才等60分钟确认", digest)
        self.assertIn("强核心开盘核心", digest)
        self.assertIn("10点确认", digest)
        self.assertIn("30分钟止损", digest)
        self.assertIn("资格、条件、可做和参与", digest)
        self.assertLess(len(digest), 500)
        self.assertNotIn("缠论原文", digest)
        self.assertNotIn("能量学", digest)
        self.assertNotIn("教你炒股票", digest)


if __name__ == "__main__":
    unittest.main()
