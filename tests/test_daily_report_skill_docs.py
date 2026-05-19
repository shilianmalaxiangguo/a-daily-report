import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _m(*parts):
    return "".join(parts)


class DailyReportSkillDocsTest(unittest.TestCase):
    def _read(self, relative_path):
        path = ROOT / relative_path
        self.assertTrue(path.exists(), f"Missing required skill doc: {relative_path}")
        return path.read_text(encoding="utf-8")

    def _latest_public_report_paths(self):
        index_path = ROOT / "snap-ui" / "public" / "data" / "daily-reports" / "index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        latest = (index.get("reports") or [{}])[0]
        paths = []
        for variant in latest.get("availableVariants") or []:
            content_path = ((latest.get("variants") or {}).get(variant) or {}).get("contentPath")
            if content_path:
                paths.append(ROOT / "snap-ui" / "public" / content_path.lstrip("/"))
        return paths

    def test_skill_routes_natural_language_intents_and_references(self):
        skill = self._read("SKILL.md")

        for intent in [
            "generate_report",
            "review_report_output",
            "fix_report_defect",
            "review_trade_case",
            "extract_workflow_memory",
            "optimize_skill",
        ]:
            self.assertIn(intent, skill)

        for reference in [
            "references/report-contract.md",
            "references/memory-governance.md",
            "references/verification.md",
        ]:
            self.assertIn(reference, skill)

        self.assertIn("natural-language", skill)
        self.assertIn("users do not need to remember commands", skill)
        self.assertNotIn("workflow_memory_runtime.py", skill)
        self.assertNotIn("data/workflow_memory.json", skill)

    def test_skill_preserves_report_optimization_priority_order(self):
        skill = self._read("SKILL.md")
        priorities = [
            "report acceptance audit",
            "structured history",
            "only-focus audit",
            "entry-cycle calibration",
            "workflow memory",
            "skill refactor",
        ]

        positions = [skill.index(priority) for priority in priorities]
        self.assertEqual(positions, sorted(positions))

    def test_references_state_memory_governance_and_safety_rules(self):
        report_contract = self._read("references/report-contract.md")
        memory_governance = self._read("references/memory-governance.md")
        verification = self._read("references/verification.md")
        combined = "\n".join([report_contract, memory_governance, verification])

        for required in [
            "review artifacts only",
            "manual apply only",
            "independent evidence",
            "latest user instruction overrides memory",
            "workflow memory is not stock tracking memory",
            "no auto-apply",
            "do not build a memory platform",
            "not a command manual",
        ]:
            self.assertIn(required, combined)

    def test_future_change_specs_default_to_inherited_report_contract(self):
        skill = self._read("SKILL.md")
        report_contract = self._read("references/report-contract.md")
        combined = "\n".join([skill, report_contract])

        for required in [
            "Future Change Inheritance",
            "delta spec",
            "default inherit",
            "report contract",
            "unless the latest user instruction explicitly overrides it",
            "new report requests do not need to restate existing guardrails",
        ]:
            self.assertIn(required, combined)

    def test_monthly_rhythm_contract_names_attack_position_states(self):
        skill = self._read("SKILL.md")
        report_contract = self._read("references/report-contract.md")
        combined = "\n".join([skill, report_contract])

        for required in [
            "Trading Rhythm Base",
            "Monthly Trading Rhythm",
            "Attack Position States",
            "raises evidence requirements but no longer automatically caps position",
            "0% = no participation",
            "50% = standard attack",
            "100% = full attack",
            "进攻仓位三态",
            "profit cushion",
            "invalidation price",
            "Profit is not a downgrade trigger",
            "月10cm is not a low bar",
            "attack-month acceptance line",
            "not a monthly KPI",
            "15% is excellent",
            "20% is market-gift territory",
            "100% courage",
            "0% patience",
            "4/8/10",
            "Calendar earnings months",
            "data and news are raw material",
            "processing layer",
            "participation script",
            "auction, first minutes, board, reseal, missed-entry, and cancellation",
            "six checks",
        ]:
            self.assertIn(required, combined)

    def test_report_contract_retires_legacy_conservative_sizing(self):
        skill = self._read("SKILL.md")
        report_contract = self._read("references/report-contract.md")
        v2_spec = self._read("docs/superpowers/specs/2026-04-25-daily-report-v2-design.md")
        combined = "\n".join([skill, report_contract])

        for required in [
            "Legacy conservative sizing is removed",
            "0/50/100 only",
            "Do not answer uncertainty by shrinking every opportunity",
            "0% / 不参与",
            "50% / 标准进攻",
            "100% / 核心进攻",
            "scenario cancellation",
            "invalidation price",
        ]:
            self.assertIn(required, combined)
        self.assertNotIn("空仓 / 短线 / 波段 / 尾盘量化例外", v2_spec)
        self.assertNotIn("空仓 / 短线确认", v2_spec)

    def test_participation_script_is_persisted_to_decision_ledger_contract(self):
        skill = self._read("SKILL.md")
        report_contract = self._read("references/report-contract.md")
        context = self._read("CONTEXT.md")
        combined = "\n".join([skill, report_contract, context])

        for required in [
            "planned_participation",
            "本地判断账本",
            "判断账本快照",
            "machine-readable",
            "participation window, position state, auction, first-minutes, board, reseal, missed-entry, and cancellation",
            "source_tier",
            "entry_timing",
            "buy_window",
            "open_core",
            "ten_confirm",
            "tail_exception",
            "no_trade",
            "snap-ui must consume `planned_participation` from the decision-ledger artifact",
            "case-level and mention-level",
            "compare tomorrow's behavior against the designed scenario",
            "跟踪周期",
            "25个交易日",
            "visible participation script",
        ]:
            self.assertIn(required, combined)

    def test_participation_review_contract_names_replay_quality_labels(self):
        skill = self._read("SKILL.md")
        report_contract = self._read("references/report-contract.md")
        context = self._read("CONTEXT.md")
        combined = "\n".join([skill, report_contract, context])

        for required in [
            "participation_review",
            "参与预演复盘",
            "预演命中",
            "预演作废",
            "错过后方案命中",
            "预演过早",
            "auction_matched",
            "first_minutes_accepted",
            "board_sealed",
            "reseal_success",
            "sector_supported",
            "cancellation_triggered",
            "primary_unavailable",
            "missed_action_worked",
            "participation_review_status",
            "判断账本索引",
            "snap-ui",
        ]:
            self.assertIn(required, combined)

    def test_skill_and_report_contract_inherit_reasoning_mode_contract(self):
        skill = self._read("SKILL.md")
        report_contract = self._read("references/report-contract.md")
        reasoning_contract = self._read("references/reasoning-mode-contract.md")
        combined = "\n".join([skill, report_contract, reasoning_contract])

        for required in [
            "references/reasoning-mode-contract.md",
            "reasoning decision JSON",
            "no-API first",
            "current-conversation reasoning",
            "do not expose chain-of-thought",
            "deterministic facts",
            "bounded decisions",
            "future report changes inherit both report contract and reasoning contract",
        ]:
            self.assertIn(required, combined)

    def test_skill_and_report_contract_inherit_anti_noise_price_action_boundary(self):
        skill = self._read("SKILL.md")
        report_contract = self._read("references/report-contract.md")
        boundary_spec = self._read(
            "docs/superpowers/specs/2026-05-03-daily-report-anti-noise-price-action-boundary-design.md"
        )
        combined = "\n".join([skill, report_contract, boundary_spec])

        for required in [
            "2026-05-03-daily-report-anti-noise-price-action-boundary-design.md",
            "推演型工具不得进入日报主链",
            "交易经验可以被吸收，但必须字段化、规则化、复盘化",
            "价格行为字段",
            "上涨斜率",
            "回撤比例",
            "突破后承接",
            "加速后衰竭",
            "不能以自由叙事进入日报主链",
        ]:
            self.assertIn(required, combined)

    def test_skill_and_report_contract_preserve_fieldized_energy_theory_t1_avoidance(self):
        skill = self._read("SKILL.md")
        report_contract = self._read("references/report-contract.md")
        combined = "\n".join([skill, report_contract])

        for required in [
            "能量聚集",
            "能量释放",
            "上涨角度",
            "下跌角度",
            "上涨幅度",
            "调整幅度",
            "等速运动最省力",
            "速度变化",
            "T+1避亏",
            "津药药业",
            "2026-04-08",
            "2026-04-09",
            "不介入",
        ]:
            self.assertIn(required, combined)

    def test_skill_and_report_contract_preserve_newton_iteration_decision_discipline(self):
        skill = self._read("SKILL.md")
        report_contract = self._read("references/report-contract.md")
        combined = "\n".join([skill, report_contract])

        for required in [
            "Newton iteration decision discipline",
            "coarse 1.0 judgment",
            "option sample feedback",
            "do not wait for a perfect answer",
            "强量转弱",
            "缩量冲高",
            "放量下杀",
            "上涨斜率放缓",
            "T+1 next-day action",
            "fieldized decision fields",
        ]:
            self.assertIn(required, combined)

    def test_llm_wiki_preserves_chinese_chanlun_nodes_and_boundaries(self):
        skill = self._read("SKILL.md")
        wiki_readme = self._read("wiki/README.md")
        price_action = self._read("wiki/交易思想/价格行为与能量框架.md")
        trend_holding = self._read("wiki/交易思想/启动板与趋势持股短板.md")
        sector_mainline = self._read("wiki/板块补充/板块中枢与主线延续.md")
        chanlun_system = self._read("wiki/交易思想/缠论体系.md")
        chanlun_boundary = self._read("wiki/交易思想/缠论-日报使用边界.md")
        raw_index = self._read("wiki/资料库/缠论原文索引.md")

        for path in [
            "wiki/交易思想/价格行为与能量框架.md",
            "wiki/交易思想/启动板与趋势持股短板.md",
            "wiki/交易思想/缠论-中枢.md",
            "wiki/交易思想/缠论-背驰.md",
            "wiki/交易思想/缠论-分型笔线段.md",
            "wiki/交易思想/缠论-买卖点.md",
            "wiki/交易思想/缠论-级别联立.md",
            "wiki/个股分析/缠论结构观察模板.md",
            "wiki/板块补充/板块中枢与主线延续.md",
            "wiki/个股炒作逻辑复盘/缠论视角复盘模板.md",
        ]:
            self._read(path)

        combined = "\n".join(
            [skill, wiki_readme, price_action, trend_holding, sector_mainline, chanlun_system, chanlun_boundary, raw_index]
        )

        for required in [
            "LLM Wiki",
            "wiki/交易思想/缠论体系.md",
            "个股分析",
            "交易思想",
            "板块补充",
            "个股炒作逻辑复盘",
            "中文节点",
            "人可读",
            "AI可引用",
            "原文不直接进入日报主链",
            "日线结构中枢定环境",
            "60分钟确认",
            "30分钟止损",
            "市场环境优先，个股结构执行",
            "MACD只能作为辅助",
            "不看基本面",
            "角度与幅度",
            "上涨和下跌的角度和幅度",
            "启动板",
            "短线触发转趋势观察仓",
            "当前短板",
            "能力空白",
            "缺失字段",
            "卖出原因可复盘",
            "风险信号和情绪信号",
            "来源保真",
            "原文可直接支持",
            "系统化抽象",
            "不能归因给原文",
            "不把系统化抽象冒充原文",
            "数学期望与回撤控制",
            "低回撤",
            "攻击频次",
            "亏损边界",
            "先避免大亏损，再追求偶尔向上大盈利",
            "胜率赔率",
            "利润奔跑",
            "集中大赚",
            "代价和平衡",
            "板块节奏",
            "量化环境",
            "单一龙头定价权",
            "能量聚集",
            "能量释放",
            "稳定知识写入 LLM Wiki",
            ".cleanup-archive/a-daily-report-2026-05-07/chanlun",
        ]:
            self.assertIn(required, combined)

    def test_llm_wiki_contains_report_surface_wording_contract(self):
        wiki_readme = self._read("wiki/README.md")
        wording_node = self._read("wiki/交易思想/日报术语契约.md")
        combined = "\n".join([wiki_readme, wording_node])

        for required in [
            "日报术语契约",
            "买入资格",
            "资格",
            "条件",
            "可做",
            "禁用旧术语",
            "术语净化",
            "旧工程口径",
            "日志",
            "前台",
        ]:
            self.assertIn(required, combined)

    def test_llm_wiki_contains_tushare_first_data_source_contract(self):
        skill = self._read("SKILL.md")
        wiki_readme = self._read("wiki/README.md")
        data_source_node = self._read("wiki/运行契约/日报数据源契约.md")
        combined = "\n".join([skill, wiki_readme, data_source_node])

        for required in [
            "Tushare-first",
            "快速稳定高效",
            "fresh daily generation",
            "snap-ui public data",
            "akshare",
            "iwencai",
            "fallback only",
            "https://tushare.pro/document/2?doc_id=14",
            "ths_hot",
            "limit_list_ths",
            "ths_daily",
            "moneyflow_ind_ths",
            "top_list",
            "new_share",
            "异动检测触发判定补价",
            "quicktiny.exchange_monitor",
            "quote_provider",
            "特色源边界",
            "stock_hot_rank",
            "limit_pool_snapshot",
            "sector_hot_plates",
            "sector_change_rank",
            "sector_fund_flow",
            "lhb_snapshot",
            "new_stock_calendar",
            "tests.test_tushare_input_runtime",
        ]:
            self.assertIn(required, combined)

    def test_skill_docs_preserve_python314_and_tushare_gateway_runtime_contract(self):
        skill = self._read("SKILL.md")
        data_source_node = self._read("wiki/运行契约/日报数据源契约.md")
        verification = self._read("references/verification.md")
        combined = "\n".join([skill, data_source_node, verification])

        for required in [
            "Python 3.14-first",
            "do not silently fall back to 3.11",
            "Tushare gateway",
            "TUSHARE_HTTP_URL",
            "http://118.89.66.41:8010/",
            "create_tushare_pro_api",
        ]:
            self.assertIn(required, combined)

    def test_cloudflare_module_mime_reflection_is_recorded(self):
        reflection = self._read("docs/ops/reflections/2026-05-13-cloudflare-pages-module-mime.md")

        for required in [
            "Cloudflare Pages",
            "module MIME",
            "text/html",
            "application/javascript",
            "clean .output and dist",
            "verify-pages-module-assets",
            "do not manually redeploy before identifying the bad asset URL",
        ]:
            self.assertIn(required, reflection)

    def test_llm_wiki_contains_snap_ui_publish_contract(self):
        wiki_readme = self._read("wiki/README.md")
        publish_node = self._read("wiki/运行契约/snap-ui发布契约.md")
        combined = "\n".join([wiki_readme, publish_node])

        for required in [
            "Cloudflare Pages",
            "module MIME",
            "application/javascript",
            "verify-pages-module-assets",
            "clean .output and dist",
            "develop",
            "tests/unit/publicStaticDataContract.test.ts",
        ]:
            self.assertIn(required, combined)

    def test_daily_report_entry_docstring_keeps_tushare_as_primary_source(self):
        entry = self._read("scripts/daily_report_entry_demo.py")

        self.assertIn("基础市场事实与 snap-ui public data：Tushare-first", entry)
        self.assertIn("指数数据：Tushare index_daily（首选）", entry)
        self.assertIn("两市成交额：Tushare daily amount（首选）", entry)
        self.assertIn("板块热榜：Tushare ths_hot", entry)
        self.assertIn("行业资金流向：Tushare moneyflow_ind_ths", entry)
        self.assertIn("板块涨跌幅排行：Tushare ths_index + ths_daily", entry)
        self.assertIn("龙虎榜数据：Tushare top_list", entry)
        self.assertIn("新股日历：Tushare new_share", entry)
        self.assertNotIn("指数数据：AkShare 指数日线（首选）", entry)
        self.assertNotIn("两市成交额：AkShare 指数成交额（首选）", entry)

    def test_scripts_do_not_hardcode_legacy_user_visible_wording(self):
        forbidden = (
            _m("门", "控"),
            _m("闸", "门"),
            _m("开", "闸"),
            _m("放", "行"),
            _m("执行", "权"),
            _m("执行", "权限"),
            _m("买入", "权限"),
            _m("开", "火"),
            _m("不", "开", "火"),
        )
        allowed_paths = {
            "scripts/knowledge/llm_wiki_context.py",
            "scripts/daily_report_entry_demo.py",
        }
        allowed_prefixes = ("scripts/data/",)
        offenders = []

        for path in sorted((ROOT / "scripts").rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            if rel in allowed_paths or rel.startswith(allowed_prefixes):
                continue
            text = path.read_text(encoding="utf-8")
            for marker in forbidden:
                if marker in text:
                    offenders.append(f"{rel}: {marker}")

        self.assertEqual([], offenders)

    def test_scripts_do_not_surface_ma_convergence_as_decision_reason(self):
        offenders = []
        marker = _m("均线", "粘合")

        for folder in ("scripts/report", "scripts/selection", "scripts/domains/execution_chain"):
            for path in sorted((ROOT / folder).rglob("*.py")):
                rel = path.relative_to(ROOT).as_posix()
                text = path.read_text(encoding="utf-8")
                if marker in text:
                    offenders.append(rel)

        self.assertEqual([], offenders)

    def test_context_docs_wiki_and_public_reports_do_not_contain_retired_strategy_markers(self):
        forbidden = (
            _m("门", "控"),
            _m("闸", "门"),
            _m("开", "闸"),
            _m("放", "行"),
            _m("执行", "权"),
            _m("执行", "权限"),
            _m("买入", "权限"),
            _m("开", "火"),
            _m("不", "开", "火"),
            _m("均线", "粘合"),
            _m("B档", "30%"),
            _m("A-档", "50%"),
            _m("A", "档", "80%", "-100%"),
            _m("30%", "条件试错"),
            _m("30%", "试错"),
            _m("最多", "30%"),
            _m("最多", "半仓"),
            "明日前30分钟先确认环境",
            "真正买点一律等60分钟",
            "买点一律等60分钟",
            "开盘前30分钟",
            "这30分钟只确认环境",
            "前30分钟只确认环境",
            "不抢买点",
            _m("买点必须", "等60分钟"),
            "即便满足价格条件，也要等60分钟",
        )
        roots = [
            ROOT / "SKILL.md",
            ROOT / "CONTEXT.md",
            ROOT / "references",
            ROOT / "wiki",
            ROOT / "docs" / "superpowers" / "specs",
            ROOT / "docs" / "superpowers" / "plans",
            *self._latest_public_report_paths(),
        ]
        offenders = []
        for root in roots:
            paths = [root] if root.is_file() else sorted(root.rglob("*"))
            for path in paths:
                if not path.is_file():
                    continue
                if path.suffix not in {".md", ".json", ".py", ".ts", ".vue"}:
                    continue
                rel = path.relative_to(ROOT).as_posix()
                text = path.read_text(encoding="utf-8")
                for marker in forbidden:
                    if marker in text:
                        offenders.append(f"{rel}: {marker}")

        self.assertEqual([], offenders)

    def test_scripts_do_not_restore_universal_wait_for_60_minute_confirmation(self):
        forbidden = (
            "明日前30分钟先确认环境",
            "真正买点一律等60分钟",
            "买点一律等60分钟",
            "开盘前30分钟",
            "这30分钟只确认环境",
            "前30分钟只确认环境",
            "不抢买点",
            _m("买点必须", "等60分钟"),
            "即便满足价格条件，也要等60分钟",
        )
        offenders = []
        for folder in ("scripts/report", "scripts/domains/execution_chain", "scripts/hooks"):
            for path in sorted((ROOT / folder).rglob("*.py")):
                rel = path.relative_to(ROOT).as_posix()
                text = path.read_text(encoding="utf-8")
                for marker in forbidden:
                    if marker in text:
                        offenders.append(f"{rel}: {marker}")

        self.assertEqual([], offenders)

    def test_verification_reference_names_practical_commands(self):
        verification = self._read("references/verification.md")

        for required in [
            "venv/bin/python scripts/daily_report_entry_demo.py",
            "scripts/report/report_acceptance_audit.py",
            "venv/bin/python -m unittest",
            "tests.test_report_acceptance_audit",
            "tests.test_entry_plan_node_runtime",
            "git diff --check",
        ]:
            self.assertIn(required, verification)


if __name__ == "__main__":
    unittest.main()
