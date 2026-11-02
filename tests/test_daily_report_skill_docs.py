"""Current documentation must follow the rebuilt Wiki, not archived rules."""
import ast
import hashlib
import json
import unittest
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from report.surface_wording import sanitize_user_visible_text


def _m(*parts):
    return "".join(parts)


class DailyReportSkillDocsTest(unittest.TestCase):
    def read(self, relative_path):
        path = ROOT / relative_path
        self.assertTrue(path.exists(), f"Missing current document: {relative_path}")
        return path.read_text(encoding="utf-8")

    def test_skill_routes_requests_to_current_wiki_and_report_contract(self):
        skill = self.read("SKILL.md")
        for intent in (
            "generate_report", "review_report_output", "fix_report_defect",
            "review_trade_case", "extract_workflow_memory", "optimize_skill",
        ):
            self.assertIn(intent, skill)
        for path in (
            "wiki/README.md", "references/report-contract.md",
            "references/verification.md", "references/memory-governance.md",
        ):
            self.assertIn(path, skill)
        self.assertIn("do not need to remember commands", skill)

    def test_current_docs_use_only_small_cap_and_the_confirmed_commission(self):
        wiki = self.read("wiki/README.md")
        values = self.read("wiki/交易思想/小盘轮换策略.md")
        skill = self.read("SKILL.md")
        contract = self.read("references/report-contract.md")
        current = "\n".join((wiki, values, skill, contract))
        for phrase in (
            "为了赚钱理解市场", "小盘轮换 v0.3", "5只名单加3只备选", "不上杠杆",
            "万一免五", "0.01%", "无最低收费", "2025-02-28", "2026-10-29",
            "单期模拟", "原买价", "淘汰赛",
        ):
            self.assertIn(phrase, current)
        for retired in (
            "0/50/100 only", "0%不参与", "50%条件执行", "100%核心进攻",
            "planned_participation", "09:50-10:10", "月10cm",
        ):
            self.assertNotIn(retired, skill + contract)

    def test_readme_and_skill_make_sector_reading_default_without_sector_exclusivity(self):
        readme = self.read("README.md")
        skill = self.read("SKILL.md")
        prd = self.read("docs/plans/2026-10-22-daily-report-framework-rebuild-prd.md")
        self.assertIn("当前入口只生成桌面板块阅读页", readme)
        self.assertIn("not a rule that all opportunities must begin from a sector", skill)
        self.assertIn("不传 `--output-mode`", prd)
        self.assertIn("--replay", readme)
        self.assertIn("--historical-rebuild", readme)
        self.assertIn("scripts/daily_report_current.py", readme)
        self.assertIn("只定位已有旧完整版", readme)

    def test_archived_readme_release_notes_are_not_current_rules(self):
        readme = self.read("README.md")
        self.assertIn("历史维护记录已移到", readme)
        archived = self.read("docs/archive/daily-report-framework/2026-11-02/README-release-history.md")
        self.assertIn("## 历史版本记录", archived)
        self.assertIn("B1/B2", archived)
        self.assertIn("10-20", archived)

    def test_root_context_and_issues_do_not_reinstate_retired_rules(self):
        context = self.read("CONTEXT.md")
        issues = self.read("issue.md")
        for text in (context, issues):
            self.assertIn("2026-10-22", text)
            self.assertIn("wiki/README.md", text)
            self.assertIn("docs/archive/daily-report-framework/2026-10-22/", text)
        for retired in (
            "进攻仓位三态", "0%/50%/100%", "must carry one", "不可改变项",
            "不让决策 LLM Wiki 反向改写",
        ):
            self.assertNotIn(retired, context + issues)
        self.assertIn("目标日", context)
        self.assertIn("不默认空仓", context)
        self.assertIn("不再是待实施队列", issues)

    def test_replaced_root_documents_keep_their_originals(self):
        archive = "docs/archive/daily-report-framework/2026-10-22/"
        self.assertTrue(self.read(archive + "CONTEXT.md").startswith("# Daily Report Decision Context"))
        self.assertIn("记录日期：2026-08-03", self.read(archive + "issue.md"))

    def test_retired_main_tests_are_archived_with_proof_and_not_run_against_current_entry(self):
        manifest = json.loads(self.read('docs/archive/daily-report-framework/2026-10-22/retired-entry-test-manifest.json'))
        renamed = json.loads(self.read('docs/archive/daily-report-framework/2026-11-02/retired-strategy-tests-manifest.json'))
        current_paths = {item['source']: item['archive'] for item in renamed['files']}
        for item in manifest['files']:
            original = (ROOT / item['archive']).read_bytes()
            self.assertEqual(hashlib.sha256(original).hexdigest(), item['sha256'])
            current = self.read(current_paths.get(item['source'], item['source']))
            tree = ast.parse(current)
            for cls in tree.body:
                if not isinstance(cls, ast.ClassDef):
                    continue
                for method in cls.body:
                    if isinstance(method, ast.FunctionDef) and method.name.startswith('test_'):
                        self.assertNotIn('daily_report_entry_demo.main', ast.get_source_segment(current, method))

    def test_frozen_execution_suites_preserve_bytes_and_leave_default_discovery(self):
        manifest = json.loads(self.read('docs/archive/daily-report-framework/2026-11-02/retired-strategy-tests-manifest.json'))
        sources = {item['source'] for item in manifest['files']}
        for name in ('position_sizing_runtime', 'formal_account_decision', 'two_layer_decision_payload',
                     'sniper_target_derivation', '20260519_report_decision_surface'):
            self.assertIn(f'tests/test_{name}.py', sources)
        for item in manifest['files']:
            self.assertFalse((ROOT / item['source']).exists(), item['source'])
            archived = ROOT / item['archive']
            self.assertFalse(archived.match('test*.py'))
            self.assertEqual(hashlib.sha256(archived.read_bytes()).hexdigest(), item['sha256'])
        search_rules = self.read('.rgignore').splitlines()
        self.assertIn('/scripts/report/runtime.py', search_rules)
        self.assertNotIn('/scripts/report/runtime/', search_rules)

    def test_report_contract_preserves_truth_history_and_human_choice(self):
        contract = self.read("references/report-contract.md")
        for phrase in (
            "source fact date", "query/retrieval date", "Missing data is not zero",
            "Existing official reports and snapshots are protected",
            "not an account decision", "No test or report structure proves a trading method profitable",
            "The latest user instruction takes precedence",
        ):
            self.assertIn(phrase, contract)
        self.assertIn("Do not enforce a fixed hypothesis count", contract)
        self.assertIn("A single-stock opportunity need not wait for sector approval", contract)

    def test_current_docs_do_not_require_daily_template_analysis(self):
        contract = self.read('references/report-contract.md')
        skill = self.read('SKILL.md')
        wiki = self.read('wiki/交易思想/采样聚合与日报精简.md')
        self.assertIn('chart-first', contract)
        self.assertIn('chart-first', skill)
        self.assertIn('图表优先', wiki)
        self.assertIn('固定条件', wiki)
        self.assertNotIn('Put the current understanding near the top', contract)

    def test_retired_strategy_pages_are_marked_frozen_and_cannot_route_current_entry(self):
        frozen = {
            'wiki/交易思想/采样聚合与日报精简.md',
            'wiki/交易思想/交易反馈与方法修正.md',
            'wiki/交易思想/市场适配与策略生命周期.md',
            'wiki/交易思想/探索、目标与踏脚石.md',
        }
        for path in frozen:
            text = self.read(path)
            self.assertIn('已冻结', text, path)
            self.assertIn('当前', text, path)
        sampling = self.read('wiki/交易思想/采样聚合与日报精简.md')
        self.assertIn('当前入口不生成对应区块', sampling)
        self.assertNotIn('日报首屏先给当日解读与规则信号', sampling)
        feedback = self.read('wiki/交易思想/交易反馈与方法修正.md')
        self.assertIn('当前入口不再生成或延续这条链', feedback)

    def test_current_docs_preserve_alpha_beta_as_explicit_research_only(self):
        wiki = self.read('wiki/README.md')
        skill = self.read('SKILL.md')
        contract = self.read('references/report-contract.md')
        self.assertIn('阿尔法／贝塔', wiki)
        self.assertIn('研究', wiki)
        for text in (skill, contract):
            self.assertIn('Alpha/Beta', text)
            self.assertIn('research', text)
        self.assertIn('不进入小盘日报', wiki)
        self.assertIn('Alpha/Beta research is opt-in', skill)
        self.assertIn('frozen results remain available for explicit research', contract)

    def test_historical_prds_cannot_be_read_as_current_mobile_or_strategy_requirements(self):
        for path in (
            'docs/plans/2026-10-22-daily-report-framework-rebuild-prd.md',
            'docs/plans/2026-10-23-sector-chart-reading-todo.md',
            'docs/plans/2026-10-30-decision-dashboard-prd.md',
        ):
            text = self.read(path)
            self.assertIn('历史', text, path)
            self.assertIn('当前', text, path)
        self.assertIn('手机窗口和触摸检查不再执行',
                      self.read('docs/plans/2026-10-23-sector-chart-reading-todo.md'))

    def test_verification_uses_python314_replay_and_does_not_require_legacy_generation(self):
        verification = self.read("references/verification.md")
        for phrase in (
            ".generated/venv-py314/bin/python3.14", "tests.test_market_reading_entry",
            "scripts/daily_report_current.py 2026-10-20 --replay",
            "only when the current change is explicitly about layout or interaction",
            "official-file hashes", "only locates an existing historical original",
        ):
            self.assertIn(phrase, verification)
        self.assertNotIn("one final full generation", verification)

    def test_root_instructions_mark_old_display_rules_historical_and_use_current_replay_page(self):
        instructions = self.read('AGENTS.md')
        self.assertIn('历史展示维护记录（不适用于当前入口）', instructions)
        current_bug_flow = instructions.split('# 日报 bug 修复短口令', 1)[1].split('## 历史索引', 1)[0]
        self.assertIn('_板块日报_replay.html', current_bug_flow)
        self.assertIn('--snapshot-source replay', current_bug_flow)
        self.assertNotIn('_完整版_replay.md', current_bug_flow)
        self.assertNotIn('--overwrite-official', current_bug_flow)
        self.assertIn('full 只定位已有历史原件', instructions)

    def test_maintenance_archives_preserve_original_bytes(self):
        base = 'docs/archive/daily-report-framework/2026-11-02/'
        manifest = json.loads(self.read(base + 'maintenance-manifest.json'))
        self.assertEqual(
            {item['source'] for item in manifest['files']},
            {'README.md', 'AGENTS.md', 'references/verification.md'},
        )
        for item in manifest['files']:
            raw = (ROOT / item['archive']).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), item['sha256'])
            if item['source'] == 'README.md':
                self.assertEqual(item['sha256'], item['source_snapshot_sha256'])
                self.assertEqual(item['source_stage'], 'before_2026-11-01_strategy_cleanup')
                original = ROOT / item['source_snapshot']
                if original.is_file():
                    self.assertEqual(raw, original.read_bytes())
        self.assertLess(len(self.read('AGENTS.md').splitlines()), 120)
        self.assertNotIn('## 2026-10-30 决策仪表盘', self.read('AGENTS.md'))

    def test_old_display_maintenance_docs_route_to_current_rebuild(self):
        for name in ('readme', 'flow', 'testing'):
            with self.subTest(name=name):
                text = self.read(f'docs/daily-report-structure-optimization/{name}.md')
                notice = text.split('## ', 1)[0]
                self.assertIn('历史展示记录，不适用于当前日报入口', notice)
                self.assertIn('2026-10-22-daily-report-framework-rebuild-prd.md', notice)

    def test_retired_wiki_paths_are_not_current_skill_routes(self):
        skill = self.read("SKILL.md")
        retired = (
            "wiki/交易思想/缠论体系.md", "wiki/资料库/缠论原文索引.md",
            "wiki/运行契约/日报数据源契约.md",
        )
        for path in retired:
            self.assertFalse((ROOT / path).exists(), path)
            self.assertNotIn(path, skill)


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


    def test_user_visible_wording_rewrites_observation_permission_language(self):
        old_permission_word = _m("观察", "权")
        text = f"0%不参与不开新仓，只保留高优先级{old_permission_word}；普通{old_permission_word}只看承接。"

        sanitized = sanitize_user_visible_text(text)

        self.assertIn("高优先级观察对象", sanitized)
        self.assertIn("普通观察对象", sanitized)
        self.assertNotIn(old_permission_word, sanitized)


    def test_user_visible_wording_rewrites_pseudo_precise_trading_language(self):
        text = (
            "周期概率窗口只作条件链合并判断，不输出精确胜率；"
            "近5个已结算交易日正确率；"
            "PK决胜局（期望值模型）只看历史胜率收益；"
            "次日冲高或再涨停概率高于普通上涨样本。"
        )

        sanitized = sanitize_user_visible_text(text)

        self.assertIn("周期窗口", sanitized)
        self.assertIn("不输出精确预测", sanitized)
        self.assertIn("近5个已结算交易日复盘表现", sanitized)
        self.assertIn("过程候选最终复核", sanitized)
        self.assertIn("历史复盘样本", sanitized)
        self.assertIn("次日是否继续被资金承接需要窗口确认", sanitized)
        self.assertNotIn("周期概率窗口", sanitized)
        self.assertNotIn("正确率", sanitized)
        self.assertNotIn("精确胜率", sanitized)
        self.assertNotIn("期望值模型", sanitized)
        self.assertNotIn("历史胜率收益", sanitized)
        self.assertNotIn("概率高于普通上涨样本", sanitized)


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


if __name__ == "__main__":
    unittest.main()
