"""Generate a deterministic visual preview for the sector forward replay HTML."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from replay.sector_forward_replay import render_forward_replay_html


DEFAULT_OUTPUT = PROJECT_ROOT / "reports" / "replay" / "_style_anchor_sector_forward_replay.html"


def _style_anchor_payload():
    rows = [
        {
            "label": "09:30-09:35买 / 14:30-14:55卖（原始）",
            "short_label": "开盘买/尾盘卖",
            "buy_window_id": "open_0930_0935",
            "buy_window": "09:30-09:35",
            "sell_window_id": "late_1430_1455",
            "sell_window": "14:30-14:55",
            "exclusion": "未剔除接近涨停买点",
            "sample_count": 6,
            "all_sample_count": 6,
            "period_count": 6,
            "positive_count": 4,
            "average_return_pct": 2.2,
            "final_net_value": 1.116,
            "cumulative_return_pct": 11.6,
            "monthly_return_pct": 7.1,
            "annualized_return_pct": 129.4,
            "max_drawdown_pct": -3.2,
            "sample_text": "6/6",
            "excess_上证指数": 9.1,
            "excess_创业板指": 8.3,
            "excess_科创50": 7.8,
            "excess_中证500": 7.2,
            "excess_全A指数": 6.9,
            "excess_中证1000": 6.1,
        },
        {
            "label": "10:00-10:30买 / 10:30-11:30卖（原始）",
            "short_label": "上午买/午前卖",
            "buy_window_id": "morning_1000_1030",
            "buy_window": "10:00-10:30",
            "sell_window_id": "morning_1030_1130",
            "sell_window": "10:30-11:30",
            "exclusion": "未剔除接近涨停买点",
            "sample_count": 6,
            "all_sample_count": 6,
            "period_count": 6,
            "positive_count": 2,
            "average_return_pct": -1.4,
            "final_net_value": 0.928,
            "cumulative_return_pct": -7.2,
            "monthly_return_pct": -4.8,
            "annualized_return_pct": -53.7,
            "max_drawdown_pct": -8.6,
            "sample_text": "6/6",
            "excess_上证指数": -9.7,
            "excess_创业板指": -10.5,
            "excess_科创50": -11.0,
            "excess_中证500": -11.6,
            "excess_全A指数": -11.9,
            "excess_中证1000": -12.7,
        },
    ]
    return {
        "start_date": "2026-06-01",
        "end_date": "2026-06-12",
        "sample_count": 6,
        "notes": ["样式锚点预览，只用于观察回测 HTML 展示，不代表真实回测结论。"],
        "pairs": [],
        "summary": {
            "trade_window_matrix_summary": {
                "best_combo": {
                    "buy_window_id": "open_0930_0935",
                    "buy_window": "09:30-09:35",
                    "sell_window_id": "late_1430_1455",
                    "sell_window": "14:30-14:55",
                },
                "rows": [
                    {
                        "buy_window_id": "open_0930_0935",
                        "buy_window": "09:30-09:35",
                        "sell_window_id": "late_1430_1455",
                        "sell_window": "14:30-14:55",
                        "average_return_pct": 11.6,
                        "sample_count": 6,
                        "positive_count": 4,
                    },
                    {
                        "buy_window_id": "open_0930_0935",
                        "buy_window": "09:30-09:35",
                        "sell_window_id": "morning_1030_1130",
                        "sell_window": "10:30-11:30",
                        "average_return_pct": 3.4,
                        "sample_count": 6,
                        "positive_count": 3,
                    },
                    {
                        "buy_window_id": "morning_1000_1030",
                        "buy_window": "10:00-10:30",
                        "sell_window_id": "morning_1030_1130",
                        "sell_window": "10:30-11:30",
                        "average_return_pct": -7.2,
                        "sample_count": 6,
                        "positive_count": 2,
                    },
                    {
                        "buy_window_id": "morning_1000_1030",
                        "buy_window": "10:00-10:30",
                        "sell_window_id": "late_1430_1455",
                        "sell_window": "14:30-14:55",
                        "average_return_pct": -1.8,
                        "sample_count": 6,
                        "positive_count": 3,
                    },
                ],
                "recommended_equity_curve": {
                    "curve_points": [
                        {
                            "decision_date": "2026-06-02",
                            "buy_date": "2026-06-03",
                            "sell_date": "2026-06-04",
                            "stock": "样式样本A",
                            "return_pct": 5.2,
                            "net_value": 1.052,
                            "cumulative_return_pct": 5.2,
                            "drawdown_pct": 0.0,
                        },
                        {
                            "decision_date": "2026-06-05",
                            "buy_date": "2026-06-08",
                            "sell_date": "2026-06-09",
                            "stock": "样式样本B",
                            "return_pct": -2.6,
                            "net_value": 1.0246,
                            "cumulative_return_pct": 2.46,
                            "drawdown_pct": -2.6,
                        },
                        {
                            "decision_date": "2026-06-10",
                            "buy_date": "2026-06-11",
                            "sell_date": "2026-06-12",
                            "stock": "样式样本C",
                            "return_pct": 4.8,
                            "net_value": 1.0738,
                            "cumulative_return_pct": 7.38,
                            "drawdown_pct": 0.0,
                        },
                    ],
                    "final_net_value": 1.0738,
                    "max_drawdown_pct": -2.6,
                },
            },
            "window_performance_comparison": {
                "basis": "固定样式预览数据，覆盖正收益、负收益、矩阵深浅色和指数对比。",
                "rows": rows,
            },
            "index_benchmark_summary": {
                "rows": [
                    {"label": "上证指数", "cumulative_return_pct": 2.5, "coverage_note": "样式预览"},
                    {"label": "创业板指", "cumulative_return_pct": 3.3, "coverage_note": "样式预览"},
                    {"label": "科创50", "cumulative_return_pct": 3.8, "coverage_note": "样式预览"},
                    {"label": "中证500", "cumulative_return_pct": 4.4, "coverage_note": "样式预览"},
                    {"label": "全A指数", "cumulative_return_pct": 4.7, "coverage_note": "样式预览"},
                    {"label": "中证1000", "cumulative_return_pct": 5.5, "coverage_note": "样式预览"},
                ],
            },
            "market_breadth_summary": {
                "rows": [
                    {
                        "date": "2026-06-02",
                        "up_count": 3180,
                        "down_count": 2040,
                        "all_a_return_pct": 0.8,
                        "new_high_ratio_pct": 2.2,
                    },
                    {
                        "date": "2026-06-05",
                        "up_count": 1840,
                        "down_count": 3420,
                        "all_a_return_pct": -1.1,
                        "new_high_ratio_pct": 1.4,
                    },
                ]
            },
        },
    }


def generate_preview(output_path=DEFAULT_OUTPUT):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_forward_replay_html(_style_anchor_payload()), encoding="utf-8")
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description="生成回测 HTML 样式锚点预览")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="输出 HTML 路径，默认 reports/replay/_style_anchor_sector_forward_replay.html",
    )
    args = parser.parse_args(argv)
    path = generate_preview(args.output)
    print(path)


if __name__ == "__main__":
    main()
