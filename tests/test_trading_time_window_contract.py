import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.trading_time_window_contract import normalize_trading_time_text


class TradingTimeWindowContractTest(unittest.TestCase):
    def test_active_sources_keep_trading_windows_fixed(self):
        forbidden_phrases = [
            "60" + "分钟确认",
            "60 " + "分钟确认",
            "60" + "分钟结构确认",
            "60" + "分钟缠论确认",
            "60" + "分钟走势类型",
            "60" + "分钟定买点",
            "60" + "分钟再转强",
            "分钟确认",
            "10" + "点确认",
            "10" + "点后",
            "10" + "点承接",
            "10" + "点附近",
            "10" + "点前后",
            "10:00" + "左右买",
            "10:00" + "左右观察",
            "09:50-10:10" + "确认",
            "尾盘" + "开新仓",
            "尾盘" + "新增参与",
            "形成参与窗口后",
            "参与窗口分层确认",
            "参与窗口确认",
            "参与窗口成立",
            "参与窗口命中",
            "预演参与窗口",
            "形成参与窗口",
            "参与窗口失败",
            "参与窗口不成立",
            "参与窗口才",
        ]
        scanned_roots = [ROOT / "scripts", ROOT / "wiki"]
        allowed_files = {
            ROOT / "scripts/report/trading_time_window_contract.py",
        }
        findings = []

        for root in scanned_roots:
            for path in root.rglob("*"):
                if path in allowed_files or not path.is_file():
                    continue
                if any(part in {"data", "__pycache__"} for part in path.parts):
                    continue
                if path.suffix not in {".py", ".md"}:
                    continue
                text = path.read_text(encoding="utf-8")
                for phrase in forbidden_phrases:
                    if phrase in text:
                        findings.append(str(path.relative_to(ROOT)))

        self.assertEqual([], sorted(set(findings)))

    def test_historical_timing_text_is_normalized_to_fixed_windows(self):
        self.assertEqual(
            "09:50-10:10窗口满足条件后评估",
            normalize_trading_time_text("60分钟确认后评估"),
        )
        self.assertEqual(
            "09:50-10:10窗口内条件成立后评估",
            normalize_trading_time_text("形成参与窗口后评估"),
        )
        self.assertEqual(
            "日线定环境，09:50-10:10窗口定买点，按失效价和单笔-5%底线处理风险",
            normalize_trading_time_text("日线定环境，09:50-10:10窗口定买点，30分钟定止损"),
        )
        self.assertEqual(
            "若你有仓位，失效价失守或日内明显转弱 -> 执行减仓/止损",
            normalize_trading_time_text("若你有仓位，30分钟结构失守或日内明显转弱 -> 执行减仓/止损"),
        )
        self.assertEqual(
            "**09:50-10:10买卖窗口（09:50-10:10）**:",
            normalize_trading_time_text("**结构确认窗口（09:35-10:30）**:"),
        )
        self.assertEqual(
            "09:50-10:10窗口处理买卖",
            normalize_trading_time_text("09:50-10:10确认并处理买卖"),
        )

    def test_historical_timing_text_is_normalized_inside_nested_payloads(self):
        payload = {
            "summary": "60分钟确认后评估",
            "steps": ["形成参与窗口后评估"],
        }

        self.assertEqual(
            {
                "summary": "09:50-10:10窗口满足条件后评估",
                "steps": ["09:50-10:10窗口内条件成立后评估"],
            },
            normalize_trading_time_text(payload),
        )


if __name__ == "__main__":
    unittest.main()
