"""Compact Chinese LLM Wiki context for the daily-report pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List


WIKI_VERSION = "2026-05-13"
WIKI_SOURCE = "llm_wiki"
WIKI_LANGUAGE = "zh-CN"
ROOT = Path(__file__).resolve().parents[2]

SOURCE_PATHS = [
    "wiki/README.md",
    "wiki/交易思想/价格行为与能量框架.md",
    "wiki/交易思想/缠论体系.md",
    "wiki/交易思想/缠论-日报使用边界.md",
    "wiki/交易思想/日报术语契约.md",
    "wiki/运行契约/日报数据源契约.md",
    "wiki/运行契约/snap-ui发布契约.md",
    "wiki/交易思想/缠论-级别联立.md",
    "wiki/资料库/缠论原文索引.md",
]

FIELD_MAPPINGS = [
    "日线结构中枢定环境 -> 60分钟确认 -> 30分钟止损",
    "角度与幅度 -> 上涨斜率、回撤比例、突破后承接、加速后衰竭",
    "中枢 -> 结构区间、上沿、下沿、中轴、离开方向、回抽确认",
    "背驰 -> 动能衰减、转折风险、承接验证",
]

REPORT_BOUNDARIES = [
    "原文不直接进入日报主链",
    "MACD只能作为辅助",
    "不把理论长文搬进日报",
    "只输出字段化结论和行动边界",
    "用户可见输出不用门控/闸门/执行权/开闸/放行，改用资格/条件/可做",
]

WRITE_BOUNDARIES = [
    "稳定知识写入 LLM Wiki",
    "一次性教训写入反思",
    "skill 只写行为契约",
    "service/code 写运行逻辑",
]

DATA_SOURCE_POLICY = [
    "fresh daily generation uses Tushare-first",
    "snap-ui public data uses Tushare-first structured JSON",
    "akshare/iwencai are fallback only",
]

PUBLISH_POLICY = [
    "snap-ui publish verifies Cloudflare module assets before push",
    "develop is the Cloudflare Pages branch",
    "public data contract check runs before deploy",
]

REPORT_DIGEST_TEXT = (
    "LLM Wiki约束：交易思想只取角度与幅度、承接和速度变化；"
    "缠论只取结构字段，按日线结构中枢定环境、60分钟确认、30分钟止损执行；"
    "MACD只作辅助，原文和理论长文不进日报主链；"
    "日报前台、摘要、诊断和日志不用门控/闸门/执行权/开闸/放行，改用资格/条件/可做。"
)


def _existing_source_paths() -> List[str]:
    return [path for path in SOURCE_PATHS if (ROOT / path).exists()]


def build_llm_wiki_context() -> Dict[str, object]:
    return {
        "version": WIKI_VERSION,
        "source": WIKI_SOURCE,
        "language": WIKI_LANGUAGE,
        "source_paths": _existing_source_paths(),
        "field_mappings": list(FIELD_MAPPINGS),
        "report_boundaries": list(REPORT_BOUNDARIES),
        "write_boundaries": list(WRITE_BOUNDARIES),
        "data_source_policy": list(DATA_SOURCE_POLICY),
        "publish_policy": list(PUBLISH_POLICY),
        "report_digest_text": REPORT_DIGEST_TEXT,
    }


__all__ = ["build_llm_wiki_context"]
