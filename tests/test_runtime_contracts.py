import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _m(*parts):
    return "".join(parts)

from decision.runtime_contracts import (
    get_trade_permission_contract,
    resolve_environment_display_contract,
    resolve_environment_reason_contract,
)


class RuntimeContractsTest(unittest.TestCase):
    def test_trade_permission_marks_weak_to_strong_probe_as_pre_execute_state(self):
        result = get_trade_permission_contract(
            {
                "code": "000001",
                "sector": "军工",
                "abnormal_follow_state": "跌不下去",
            },
            mainline_name="军工",
            state_machine_snapshot={"execution_bias": "watch_only"},
            weak_to_strong_context={"active": True},
        )

        self.assertFalse(result["can_execute"])
        self.assertEqual(result["permission_label"], "主线弱转强执行预备态")
        self.assertIn("固定交易窗口", result["permission_reason"])
        self.assertIn("50%条件执行", result["permission_reason"])
        self.assertNotIn(_m("3", "0%", "条件", "试错"), result["permission_reason"])

    def test_trade_permission_maps_20cm_watch_contract_to_50_attack_preview(self):
        result = get_trade_permission_contract(
            {
                "code": "300001",
                "sector": "军工",
                "watch_source": "gem_breathing_20cm",
            },
            mainline_name="军工",
            state_machine_snapshot={"execution_bias": "watch_only"},
        )

        self.assertFalse(result["can_execute"])
        self.assertEqual(result["permission_label"], "创业板20cm预启动观察权")
        self.assertIn("50%条件执行", result["permission_reason"])
        self.assertNotIn(_m("3", "0%", "条件", "试错"), result["permission_reason"])

    def test_trade_permission_grants_conviction_execute_on_resilient_abnormal(self):
        result = get_trade_permission_contract(
            {
                "code": "000001",
                "sector": "军工",
                "abnormal_follow_state": "跌不下去",
            },
            mainline_name="军工",
            conviction_codes={"000001"},
            state_machine_snapshot={"execution_bias": "allow_execute"},
        )

        self.assertTrue(result["can_execute"])
        self.assertEqual(result["permission_label"], "重点观察确认资格")
        self.assertIn("异动后跌不下去", result["permission_reason"])

    def test_environment_display_contract_demotes_watch_only_to_defense(self):
        display = resolve_environment_display_contract(
            position_level="50%条件执行",
            final_gate={"operation_state": "进攻态", "can_new_entry": True},
            state_machine_snapshot={"execution_bias": "watch_only", "energy_state": "收缩防守"},
        )

        self.assertEqual(display["position_level"], "0%不参与")
        self.assertEqual(display["operation_state"], "防守态")
        self.assertIn("先看环境", display["headline"])

    def test_environment_reason_contract_rewrites_attack_reason_when_avoid(self):
        reason = resolve_environment_reason_contract(
            position_reason="中枢已突破，积极做多",
            environment_display={
                "position_level": "0%不参与",
                "operation_state": "撤退态",
                "headline": "环境关闭，只做等待，不做新增参与",
            },
            state_machine_snapshot={
                "execution_bias": "avoid",
                "energy_state": "收缩防守",
                "state_reason": "跌停、涨跌比或仓位限制已经进入收缩区。",
            },
        )

        self.assertIn("环境关闭", reason)
        self.assertIn("收缩防守", reason)
        self.assertNotIn("积极做多", reason)
        self.assertNotIn(_m("状态", "机"), reason)
        self.assertIn("顶层环境以执行条件为准", reason)


if __name__ == "__main__":
    unittest.main()
