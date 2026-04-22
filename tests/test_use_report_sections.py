import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from hooks.report.use_report_sections import run
from orchestrator.context_store import build_empty_context, merge_hook_patches


class UseReportSectionsTest(unittest.TestCase):
    def test_report_sections_compose_from_knowledge_and_action_plan(self):
        ctx = build_empty_context({"target_date": "2026-04-22"})
        ctx = merge_hook_patches(
            ctx,
            {
                "derived": {
                    "market_phase": {"phase": "observe"},
                    "mainline": {"primary_line": "军工"},
                    "strategy_contract": {
                        "contract_label": "conditional_entry",
                        "contract_logic_digest_text": "先选边站队，再等确认",
                    },
                    "report_stages": [
                        {"stage_key": "market_environment", "title": "市场环境", "summary": "环境放行", "status": "ready"},
                        {"stage_key": "selection_focus", "title": "主线与筛选", "summary": "军工最强", "status": "ready"},
                        {"stage_key": "execution_gate", "title": "执行门控", "summary": "等60分钟确认", "status": "blocked"},
                    ],
                },
                "decision": {
                    "execution_permission": {"label": "conditional_30"},
                    "action_plan": {
                        "action_label": "conditional_entry",
                        "headline": "沿军工保留30%条件试错",
                        "trigger": "次日完成60分钟确认",
                        "rationale": "环境未坏，主线清晰",
                    },
                },
                "knowledge": {
                    "trading_philosophy": {
                        "version": "2026-04-22",
                        "source": "skillhub",
                        "source_path": "/tmp/source.md",
                        "main_derivation_chain_text": "结构中枢周期 -> 市场环境 -> 主线",
                        "decision_gate_chain_text": "环境放行 -> 主线确认 -> 60分钟确认",
                        "execution_framework_text": "日线结构中枢定环境，60分钟定买点，30分钟定止损",
                        "contract_logic_digest_text": "先选边站队，再等确认",
                        "report_preamble_lines": ["# 2026-04-22 A股日报", "", "## 🧭 交易理念底线"],
                    }
                },
            },
        )

        result = run(ctx)

        sections = result["patches"]["sections"]
        self.assertIn("交易理念底线", sections["preamble"])
        self.assertIn("主推导链", sections["environment"])
        self.assertIn("阶段看板", sections["observation"])
        self.assertIn("selection_focus", sections["observation"])
        self.assertIn("先选边站队，再等确认", sections["observation"])
        self.assertIn("沿军工保留30%条件试错", sections["execution"])
        self.assertIn("交易思想版本：2026-04-22", sections["review"])
        self.assertIn("strategy_contract: conditional_entry", sections["summary"])
        self.assertIn("market_environment", sections["summary"])


if __name__ == "__main__":
    unittest.main()
