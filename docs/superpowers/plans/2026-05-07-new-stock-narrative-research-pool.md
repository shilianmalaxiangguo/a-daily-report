# New Stock Narrative Research Pool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a separate new-stock research channel that parses official listing dates, scores narrative association, and upgrades only qualified new stocks into the normal watch candidate pool.

**Architecture:** Keep the new-stock path as a side channel. `domains.new_stock_calendar.request` owns Sina calendar parsing, `selection.new_stock_narrative_runtime` owns scoring and timing actions, `domains.watch_candidates.infer` only appends explicit upgrades, and `input.runtime` wires the side-channel payload into the daily data result.

**Tech Stack:** Python standard library, existing `unittest` test style, existing request bundle conventions, no AkShare dependency for this feature.

---

## File Structure

- Create: `scripts/domains/new_stock_calendar/__init__.py`
  - Makes the new domain importable.
- Create: `scripts/domains/new_stock_calendar/request.py`
  - Fetches and parses Sina's official new-stock listing-date calendar.
- Create: `scripts/selection/new_stock_narrative_runtime.py`
  - Scores new-stock timing, mainline match, narrative association, market emotion, board resonance, and trade value.
- Modify: `scripts/domains/watch_candidates/infer.py`
  - Appends only explicit `new_stock_candidate_upgrades` to the normal watch-candidate pool.
- Modify: `scripts/input/runtime.py`
  - Calls the new request/scoring path and exposes `new_stock_calendar`, `new_stock_research_pool`, and `new_stock_candidate_upgrades`.
- Create: `tests/test_new_stock_calendar_request.py`
  - Protects parsing, official listing-date semantics, T-2 timing, and degraded handling.
- Create: `tests/test_new_stock_narrative_runtime.py`
  - Protects Liqi-style upgrade, T-2 cash-prep warning, and weak non-upgrade samples.
- Modify: `tests/test_watch_candidates_infer.py`
  - Protects upgrade-only append behavior.
- Modify: `tests/test_input_runtime.py`
  - Protects runtime exposure and non-fatal failure behavior.

---

### Task 1: Add Sina New-Stock Calendar Request Runtime

**Files:**
- Create: `scripts/domains/new_stock_calendar/__init__.py`
- Create: `scripts/domains/new_stock_calendar/request.py`
- Create: `tests/test_new_stock_calendar_request.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_new_stock_calendar_request.py`:

```python
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from domains.new_stock_calendar.request import (
    collect_new_stock_calendar_request_bundle,
    parse_sina_new_stock_calendar_html,
)


SINA_HTML = """
<html><body>
<table>
<tr><td><div align="center">301608</div></td>
<td><div align="center">301608</div></td>
<td><div align="center"><a>理奇智能</a></div></td>
<td><div align="center">2026-04-22</div></td>
<td><div align="center">2026-04-30</div></td>
<td><div align="right">1472</div></td>
<td><div align="right">1472</div></td>
<td><div align="right">20.00</div></td>
<td><div align="right">18.20</div></td>
<td><div align="right">1.45</div></td>
<td><div align="right">2.944</div></td>
<td><div align="right">0.01</div></td>
<td><div align="center">查看</div></td>
<td><div align="center">预测</div></td>
<td><div align="center">公告</div></td>
</tr>
<tr><td><div align="center">001365</div></td>
<td><div align="center">001365</div></td>
<td><div align="center"><a>天海电子</a></div></td>
<td><div align="center">2026-05-07</div></td>
<td><div align="center">&nbsp;</div></td>
<td><div align="right">7900</div></td>
<td><div align="right">1896</div></td>
<td><div align="right">27.19</div></td>
<td><div align="right">23.40</div></td>
<td><div align="right">1.85</div></td>
<td><div align="right">21.480</div></td>
<td><div align="right">0.00</div></td>
<td><div align="center">查看</div></td>
<td><div align="center">预测</div></td>
<td><div align="center">公告</div></td>
</tr>
</table>
</body></html>
"""


class NewStockCalendarRequestTest(unittest.TestCase):
    def test_parse_sina_calendar_uses_listing_date_not_net_issue_date(self):
        rows = parse_sina_new_stock_calendar_html(
            SINA_HTML,
            target_date="2026-04-29",
            source_url="fixture://sina",
        )

        self.assertEqual(len(rows), 1)
        item = rows[0]
        self.assertEqual(item["code"], "301608")
        self.assertEqual(item["name"], "理奇智能")
        self.assertEqual(item["net_issue_date"], "2026-04-22")
        self.assertEqual(item["listing_date"], "2026-04-30")
        self.assertEqual(item["listing_window"], "tomorrow_listing")
        self.assertEqual(item["pre_listing_action"], "focus_tomorrow_battle")
        self.assertEqual(item["days_to_listing"], 1)
        self.assertEqual(item["market"], "sz")
        self.assertEqual(item["source"], "sina_new_stock_calendar")
        self.assertEqual(item["source_status"], "success")

    def test_parse_sina_calendar_marks_t2_prepare_cash_window(self):
        rows = parse_sina_new_stock_calendar_html(SINA_HTML, target_date="2026-04-28")

        self.assertEqual(rows[0]["listing_window"], "pre_alert_t2")
        self.assertEqual(rows[0]["pre_listing_action"], "prepare_clear_cash")
        self.assertEqual(rows[0]["days_to_listing"], 2)

    def test_collect_request_bundle_is_degraded_when_fetch_fails(self):
        class Timer:
            def record(self, *args):
                return (0.01, None)

        result = collect_new_stock_calendar_request_bundle(
            "2026-04-29",
            fetch_pages=lambda page_count=2: (_ for _ in ()).throw(RuntimeError("network down")),
            timer=Timer(),
            emit=lambda message: None,
        )

        self.assertEqual(result["results"]["new_stock_calendar"], [])
        self.assertFalse(result["data_status"]["新股上市日历"])
        self.assertTrue(any(log["status"] == "error" for log in result["module_logs"]))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
python3 -m unittest tests.test_new_stock_calendar_request
```

Expected: FAIL with `ModuleNotFoundError: No module named 'domains.new_stock_calendar'`.

- [ ] **Step 3: Create the package file**

Create `scripts/domains/new_stock_calendar/__init__.py`:

```python
"""New-stock calendar request domain."""
```

- [ ] **Step 4: Implement the request runtime**

Create `scripts/domains/new_stock_calendar/request.py`:

```python
from __future__ import annotations

import datetime as _dt
import html
import re
import urllib.request

__all__ = [
    "collect_new_stock_calendar_request_bundle",
    "fetch_sina_new_stock_calendar_pages",
    "parse_sina_new_stock_calendar_html",
]

SINA_NEW_STOCK_URL = "https://vip.stock.finance.sina.com.cn/corp/go.php/vRPD_NewStockIssue/page/{page}.phtml"


def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "domains.new_stock_calendar.request",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def _strip_tags(value):
    text = re.sub(r"<[^>]+>", "", str(value or ""))
    text = html.unescape(text).replace("\xa0", " ").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip()


def _safe_float(value, default=0.0):
    try:
        text = str(value or "").replace(",", "").replace("*", "").strip()
        if not text:
            return float(default)
        return float(text)
    except (TypeError, ValueError):
        return float(default)


def _normalize_date(value):
    text = _strip_tags(value)
    if not text or text in ("-", "None"):
        return ""
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    return match.group(0) if match else ""


def _parse_date(value):
    text = _normalize_date(value)
    if not text:
        return None
    try:
        return _dt.datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def _market_from_code(code):
    code = str(code or "").strip()
    if code.startswith(("6", "5", "9")):
        return "sh"
    if code.startswith(("8", "4", "92")):
        return "bj"
    if code:
        return "sz"
    return ""


def _listing_window(listing_date, target_date):
    listing = _parse_date(listing_date)
    target = _parse_date(target_date)
    if not listing or not target:
        return "outside_window", "none", None, None
    delta = (listing - target).days
    if delta == 2:
        return "pre_alert_t2", "prepare_clear_cash", delta, 0
    if delta == 1:
        return "tomorrow_listing", "focus_tomorrow_battle", delta, 0
    if delta == 0:
        return "today_listing", "live_open_confirm", delta, 0
    if delta < 0 and abs(delta) <= 5:
        return "recently_listed", "post_listing_track", delta, abs(delta)
    if 2 < delta <= 7:
        return "upcoming_soon", "none", delta, 0
    return "outside_window", "none", delta, abs(delta) if delta < 0 else 0


def _iter_table_rows(html_text):
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", str(html_text or ""), flags=re.I | re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.I | re.S)
        if len(cells) >= 12:
            yield [_strip_tags(cell) for cell in cells]


def _normalize_record(cells, target_date="", source_url=""):
    code = re.sub(r"\D", "", cells[0] if cells else "")[:6]
    name = cells[2].strip() if len(cells) > 2 else ""
    net_issue_date = _normalize_date(cells[3] if len(cells) > 3 else "")
    listing_date = _normalize_date(cells[4] if len(cells) > 4 else "")
    if not code or not name or not listing_date:
        return None
    window, action, days_to_listing, days_since_listing = _listing_window(listing_date, target_date)
    return {
        "code": code,
        "name": name,
        "net_issue_date": net_issue_date,
        "listing_date": listing_date,
        "issue_amount_10k": _safe_float(cells[5] if len(cells) > 5 else 0),
        "online_issue_amount_10k": _safe_float(cells[6] if len(cells) > 6 else 0),
        "issue_price": _safe_float(cells[7] if len(cells) > 7 else 0),
        "pe_ratio": _safe_float(cells[8] if len(cells) > 8 else 0),
        "fundraising_yi": _safe_float(cells[10] if len(cells) > 10 else 0),
        "market": _market_from_code(code),
        "days_to_listing": days_to_listing,
        "days_since_listing": days_since_listing,
        "listing_window": window,
        "pre_listing_action": action,
        "source": "sina_new_stock_calendar",
        "source_url": source_url,
        "source_status": "success",
    }


def parse_sina_new_stock_calendar_html(html_text, target_date="", source_url=""):
    records_by_code = {}
    for cells in _iter_table_rows(html_text):
        record = _normalize_record(cells, target_date=target_date, source_url=source_url)
        if not record:
            continue
        code = record["code"]
        previous = records_by_code.get(code)
        if previous is None:
            records_by_code[code] = record
            continue
        previous_distance = abs(previous.get("days_to_listing") or 9999)
        current_distance = abs(record.get("days_to_listing") or 9999)
        if current_distance < previous_distance:
            records_by_code[code] = record
    return sorted(records_by_code.values(), key=lambda item: (item.get("listing_date", ""), item.get("code", "")))


def fetch_sina_new_stock_calendar_pages(page_count=2, opener=None):
    opener = opener or urllib.request.urlopen
    pages = []
    for page in range(1, int(page_count) + 1):
        url = SINA_NEW_STOCK_URL.format(page=page)
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with opener(request, timeout=15) as response:
            raw = response.read()
        pages.append(raw.decode("gb18030", errors="replace"))
    return pages


def collect_new_stock_calendar_request_bundle(target_date, *, fetch_pages, timer, emit, page_count=2):
    results = {"new_stock_calendar": []}
    data_status = {"新股上市日历": False}
    step_status = {"新股上市日历获取": False}
    module_logs = []
    emit("  🆕 获取新浪新股上市日历...")
    try:
        pages = fetch_pages(page_count=page_count)
        records = []
        for page in pages or []:
            records.extend(parse_sina_new_stock_calendar_html(page, target_date=target_date))
        results["new_stock_calendar"] = records
        data_status["新股上市日历"] = bool(records)
        step_status["新股上市日历获取"] = True
        elapsed, _ = timer.record("新股上市日历获取", 13)
        emit(f"   ✅ 新股上市日历: {len(records)} 条 [⏱ {elapsed:.2f}s]")
        _append_log(
            module_logs,
            "request.new_stock_calendar",
            "success" if records else "degraded",
            "已处理新浪新股上市日历请求",
            provider="sina.new_stock_calendar",
            target_keys=["new_stock_calendar"],
            record_count=len(records),
        )
    except Exception as error:
        elapsed, _ = timer.record("新股上市日历获取(失败)", 13)
        emit(f"   ⚠️ 新股上市日历失败: {error} [⏱ {elapsed:.2f}s]")
        _append_log(
            module_logs,
            "request.new_stock_calendar",
            "error",
            "新浪新股上市日历请求失败",
            provider="sina.new_stock_calendar",
            target_keys=["new_stock_calendar"],
            error=str(error),
        )
    return {
        "results": results,
        "data_status": data_status,
        "step_status": step_status,
        "module_logs": module_logs,
    }
```

- [ ] **Step 5: Run the focused tests**

Run:

```bash
python3 -m unittest tests.test_new_stock_calendar_request
```

Expected: PASS.

- [ ] **Step 6: Commit Task 1**

Run:

```bash
git add scripts/domains/new_stock_calendar/__init__.py scripts/domains/new_stock_calendar/request.py tests/test_new_stock_calendar_request.py
git commit -m "feat: add new stock calendar request"
```

---

### Task 2: Add New-Stock Narrative Scoring Runtime

**Files:**
- Create: `scripts/selection/new_stock_narrative_runtime.py`
- Create: `tests/test_new_stock_narrative_runtime.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_new_stock_narrative_runtime.py`:

```python
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from selection.new_stock_narrative_runtime import build_new_stock_research_pool


class NewStockNarrativeRuntimeTest(unittest.TestCase):
    def test_liqi_style_sample_upgrades_to_new_stock_candidate(self):
        result = build_new_stock_research_pool(
            [
                {
                    "code": "301608",
                    "name": "理奇智能",
                    "listing_date": "2026-04-30",
                    "listing_window": "tomorrow_listing",
                    "pre_listing_action": "focus_tomorrow_battle",
                    "issue_price": 20.0,
                    "fundraising_yi": 2.94,
                    "industry": "锂电设备",
                    "concept_tags": ["电池", "锂电池", "宁德时代概念"],
                    "customer_anchors": ["宁德时代", "比亚迪"],
                    "supply_chain_role": "锂电设备和原材料供应链",
                    "domestic_advantage": "中国锂电制造基础设施和工程成本优势",
                }
            ],
            target_date="2026-04-29",
            context={
                "mainline_name": "电池",
                "potential_mainlines": ["锂电池", "新能源"],
                "recent_new_stock_money_effect": "strong",
                "risk_appetite": "attack",
                "sector_resonance": {"电池": {"flow_positive": True, "change_positive": True}},
            },
        )

        research = result["new_stock_research_pool"][0]
        self.assertGreaterEqual(research["new_stock_narrative_score"], 72)
        self.assertEqual(research["pre_listing_action"], "focus_tomorrow_battle")
        self.assertTrue(research["upgrade_eligible"])
        self.assertIn("宁德时代", research["candidate_upgrade_reason"])
        self.assertEqual(result["new_stock_candidate_upgrades"][0]["_source"], "新股研究池")
        self.assertEqual(result["new_stock_candidate_upgrades"][0]["core_level"], "新股预期差候选")

    def test_t2_strong_sample_warns_prepare_cash_without_buy_wording(self):
        result = build_new_stock_research_pool(
            [
                {
                    "code": "301609",
                    "name": "强链新股",
                    "listing_date": "2026-05-09",
                    "listing_window": "pre_alert_t2",
                    "pre_listing_action": "prepare_clear_cash",
                    "issue_price": 18.0,
                    "fundraising_yi": 3.2,
                    "industry": "锂电设备",
                    "concept_tags": ["电池"],
                    "customer_anchors": ["宁德时代"],
                    "supply_chain_role": "锂电设备",
                    "domestic_advantage": "供应链成本优势",
                }
            ],
            target_date="2026-05-07",
            context={
                "mainline_name": "电池",
                "recent_new_stock_money_effect": "strong",
                "risk_appetite": "attack",
                "sector_resonance": {"电池": {"flow_positive": True}},
            },
        )

        item = result["new_stock_research_pool"][0]
        self.assertEqual(item["listing_window"], "pre_alert_t2")
        self.assertEqual(item["pre_listing_action"], "prepare_clear_cash")
        self.assertIn("准备现金", item["candidate_upgrade_reason"])
        self.assertNotIn("买入", item["candidate_upgrade_reason"])

    def test_weak_non_mainline_sample_stays_research_only(self):
        result = build_new_stock_research_pool(
            [
                {
                    "code": "001365",
                    "name": "天海电子",
                    "listing_date": "2026-05-07",
                    "listing_window": "today_listing",
                    "pre_listing_action": "live_open_confirm",
                    "issue_price": 27.19,
                    "fundraising_yi": 21.48,
                    "industry": "家用电子",
                    "concept_tags": ["消费"],
                }
            ],
            target_date="2026-05-07",
            context={
                "mainline_name": "电池",
                "recent_new_stock_money_effect": "weak",
                "risk_appetite": "watch",
                "sector_resonance": {"电池": {"flow_positive": True}},
            },
        )

        research = result["new_stock_research_pool"][0]
        self.assertFalse(research["upgrade_eligible"])
        self.assertEqual(result["new_stock_candidate_upgrades"], [])
        self.assertIn("mainline_match_score", research["new_stock_factors"])
        self.assertLess(research["new_stock_factors"]["mainline_match_score"], 20)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
python3 -m unittest tests.test_new_stock_narrative_runtime
```

Expected: FAIL with `ModuleNotFoundError: No module named 'selection.new_stock_narrative_runtime'`.

- [ ] **Step 3: Implement the narrative runtime**

Create `scripts/selection/new_stock_narrative_runtime.py`:

```python
from __future__ import annotations

__all__ = [
    "build_new_stock_research_pool",
    "score_new_stock_narrative",
    "should_upgrade_new_stock_candidate",
]

UPGRADE_THRESHOLD = 72


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _text_blob(*values):
    parts = []
    for value in values:
        if isinstance(value, (list, tuple, set)):
            parts.extend(str(item or "") for item in value)
        elif isinstance(value, dict):
            parts.extend(str(item or "") for item in value.values())
        else:
            parts.append(str(value or ""))
    return " ".join(parts)


def _contains_any(text, names):
    return any(str(name or "").strip() and str(name or "").strip() in text for name in names or [])


def _score_listing_window(window):
    return {
        "pre_alert_t2": 18,
        "tomorrow_listing": 24,
        "today_listing": 22,
        "recently_listed": 14,
        "upcoming_soon": 8,
    }.get(str(window or ""), 0)


def _score_mainline(record, context):
    mainline = str((context or {}).get("mainline_name") or "").strip()
    potential = list((context or {}).get("potential_mainlines") or [])
    text = _text_blob(
        record.get("industry"),
        record.get("sector"),
        record.get("concept_tags"),
        record.get("main_business"),
        record.get("supply_chain_role"),
    )
    if mainline and mainline in text:
        return 28
    if _contains_any(text, potential):
        return 22
    return 0


def _score_narrative(record):
    score = 0
    anchors = record.get("customer_anchors") or []
    if anchors:
        score += min(16, len(anchors) * 8)
    if str(record.get("supply_chain_role") or "").strip():
        score += 8
    if str(record.get("domestic_advantage") or "").strip():
        score += 8
    text = _text_blob(record.get("main_business"), record.get("concept_tags"), record.get("industry"))
    for anchor in ("宁德时代", "比亚迪", "华为", "英伟达", "谷歌", "特斯拉"):
        if anchor in text and anchor not in anchors:
            score += 4
    return min(score, 32)


def _score_market_emotion(context):
    effect = str((context or {}).get("recent_new_stock_money_effect") or "").strip()
    appetite = str((context or {}).get("risk_appetite") or "").strip()
    score = 0
    if effect in ("strong", "强", "hot"):
        score += 14
    elif effect in ("medium", "中"):
        score += 7
    if appetite in ("attack", "进攻", "allow_execute"):
        score += 8
    elif appetite in ("watch", "观察"):
        score += 3
    return min(score, 22)


def _score_board_resonance(record, context):
    resonance = (context or {}).get("sector_resonance") or {}
    text = _text_blob(record.get("industry"), record.get("sector"), record.get("concept_tags"))
    score = 0
    for sector, payload in resonance.items():
        if sector and sector in text and isinstance(payload, dict):
            if payload.get("flow_positive"):
                score += 7
            if payload.get("change_positive"):
                score += 6
            if payload.get("mainline_turnover_up"):
                score += 6
    return min(score, 18)


def _score_trade_value(record):
    issue_price = _safe_float(record.get("issue_price"))
    fundraising = _safe_float(record.get("fundraising_yi"))
    score = 8
    if 5 <= issue_price <= 35:
        score += 8
    elif issue_price > 0:
        score += 3
    if 0 < fundraising <= 8:
        score += 6
    elif fundraising > 0:
        score += 2
    return min(score, 18)


def should_upgrade_new_stock_candidate(scored_record):
    factors = (scored_record or {}).get("new_stock_factors") or {}
    return bool(
        _safe_float((scored_record or {}).get("new_stock_narrative_score")) >= UPGRADE_THRESHOLD
        and (scored_record or {}).get("listing_window") in ("pre_alert_t2", "tomorrow_listing", "today_listing", "recently_listed", "upcoming_soon")
        and _safe_float(factors.get("mainline_match_score")) >= 20
        and _safe_float(factors.get("narrative_association_score")) >= 18
        and max(_safe_float(factors.get("market_emotion_score")), _safe_float(factors.get("board_resonance_score"))) >= 10
    )


def _build_reason(scored):
    anchors = "、".join(scored.get("customer_anchors") or [])
    parts = []
    action = scored.get("pre_listing_action")
    if action == "prepare_clear_cash":
        parts.append("T-2预警，准备现金")
    elif action == "focus_tomorrow_battle":
        parts.append("明日上市，可博弈新股")
    elif action == "live_open_confirm":
        parts.append("今日上市，只看开盘承接")
    elif action == "post_listing_track":
        parts.append("上市后跟踪承接")
    if scored.get("listing_window"):
        parts.append(scored.get("listing_window"))
    if scored.get("matched_mainline"):
        parts.append(f"{scored['matched_mainline']}主线")
    if anchors:
        parts.append(anchors)
    if scored.get("supply_chain_role"):
        parts.append(str(scored.get("supply_chain_role")))
    return " / ".join(parts) or "新股研究池观察"


def score_new_stock_narrative(record, context=None, target_date=""):
    scored = dict(record or {})
    context = context or {}
    factors = {
        "listing_window_score": _score_listing_window(scored.get("listing_window")),
        "mainline_match_score": _score_mainline(scored, context),
        "narrative_association_score": _score_narrative(scored),
        "market_emotion_score": _score_market_emotion(context),
        "board_resonance_score": _score_board_resonance(scored, context),
        "trade_value_score": _score_trade_value(scored),
    }
    total = sum(factors.values())
    scored["new_stock_factors"] = factors
    scored["new_stock_narrative_score"] = min(100, total)
    scored["matched_mainline"] = str(context.get("mainline_name") or "").strip() if factors["mainline_match_score"] >= 20 else ""
    scored["upgrade_eligible"] = should_upgrade_new_stock_candidate(scored)
    scored["candidate_upgrade_reason"] = _build_reason(scored)
    return scored


def _to_candidate(scored):
    return {
        "code": scored.get("code", ""),
        "name": scored.get("name", ""),
        "sector": scored.get("industry") or scored.get("sector") or scored.get("matched_mainline", ""),
        "turnover": scored.get("turnover", 1),
        "_source": "新股研究池",
        "watch_source": "new_stock_research_pool",
        "core_level": "新股预期差候选",
        "candidate_upgrade_reason": scored.get("candidate_upgrade_reason", ""),
        "new_stock_narrative_score": scored.get("new_stock_narrative_score", 0),
        "new_stock_factors": scored.get("new_stock_factors", {}),
        "listing_date": scored.get("listing_date", ""),
        "listing_window": scored.get("listing_window", ""),
        "pre_listing_action": scored.get("pre_listing_action", ""),
    }


def build_new_stock_research_pool(new_stock_calendar=None, target_date="", context=None):
    research_pool = [
        score_new_stock_narrative(record, context=context, target_date=target_date)
        for record in new_stock_calendar or []
        if isinstance(record, dict)
    ]
    upgrades = [_to_candidate(item) for item in research_pool if item.get("upgrade_eligible")]
    return {
        "new_stock_research_pool": research_pool,
        "new_stock_candidate_upgrades": upgrades,
    }
```

- [ ] **Step 4: Run the focused tests**

Run:

```bash
python3 -m unittest tests.test_new_stock_narrative_runtime
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add scripts/selection/new_stock_narrative_runtime.py tests/test_new_stock_narrative_runtime.py
git commit -m "feat: score new stock narrative pool"
```

---

### Task 3: Append Only Qualified New-Stock Upgrades To Watch Candidates

**Files:**
- Modify: `scripts/domains/watch_candidates/infer.py`
- Modify: `tests/test_watch_candidates_infer.py`

- [ ] **Step 1: Write the failing tests**

Add these methods to `WatchCandidatesInferTest` in `tests/test_watch_candidates_infer.py`:

```python
    def test_new_stock_research_pool_does_not_pollute_candidates_without_upgrade(self):
        result = build_watch_candidate_pool_bundle(
            {
                "turnover_rank": [{"code": "000002", "name": "成交额二号", "turnover": 123.4}],
                "new_stock_research_pool": [
                    {"code": "301608", "name": "理奇智能", "new_stock_narrative_score": 95}
                ],
            },
            emit=lambda message: None,
        )

        self.assertEqual([item["code"] for item in result["results"]["candidates"]], ["000002"])
        self.assertEqual(result["results"]["added_count"].get("new_stock"), 0)

    def test_new_stock_candidate_upgrades_are_appended_with_source_tags(self):
        result = build_watch_candidate_pool_bundle(
            {
                "turnover_rank": [{"code": "000002", "name": "成交额二号", "turnover": 123.4}],
                "new_stock_candidate_upgrades": [
                    {
                        "code": "301608",
                        "name": "理奇智能",
                        "sector": "电池",
                        "turnover": 1,
                        "_source": "新股研究池",
                        "watch_source": "new_stock_research_pool",
                        "core_level": "新股预期差候选",
                        "candidate_upgrade_reason": "明日上市 / 电池主线 / 宁德时代",
                        "new_stock_narrative_score": 92,
                        "listing_date": "2026-04-30",
                        "listing_window": "tomorrow_listing",
                        "pre_listing_action": "focus_tomorrow_battle",
                    }
                ],
            },
            emit=lambda message: None,
        )

        candidates = result["results"]["candidates"]
        upgraded = next(item for item in candidates if item["code"] == "301608")
        self.assertEqual(upgraded["_source"], "新股研究池")
        self.assertEqual(upgraded["watch_source"], "new_stock_research_pool")
        self.assertEqual(upgraded["core_level"], "新股预期差候选")
        self.assertEqual(result["results"]["added_count"]["new_stock"], 1)
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
python3 -m unittest tests.test_watch_candidates_infer
```

Expected: FAIL because `added_count["new_stock"]` is absent and upgrades are not appended.

- [ ] **Step 3: Modify candidate pool assembly**

In `scripts/domains/watch_candidates/infer.py`, inside `build_watch_candidate_pool_bundle`, change:

```python
    added_count = {"zt": 0, "tr": 0, "lb": 0, "hot": 0, "lhb": 0}
```

to:

```python
    added_count = {"zt": 0, "tr": 0, "lb": 0, "hot": 0, "lhb": 0, "new_stock": 0}
```

After the LHB loop, add:

```python
    for stock in all_data.get("new_stock_candidate_upgrades", []) or []:
        if safe_add_candidate(stock, "新股研究池", default_turnover=stock.get("turnover", 1)):
            code = stock.get("code", "") or stock.get("代码", "")
            if code in candidates_dict:
                candidates_dict[code].update(
                    {
                        "_source": "新股研究池",
                        "watch_source": stock.get("watch_source", "new_stock_research_pool"),
                        "core_level": stock.get("core_level", "新股预期差候选"),
                        "candidate_upgrade_reason": stock.get("candidate_upgrade_reason", ""),
                        "new_stock_narrative_score": stock.get("new_stock_narrative_score", 0),
                        "new_stock_factors": stock.get("new_stock_factors", {}),
                        "listing_date": stock.get("listing_date", ""),
                        "listing_window": stock.get("listing_window", ""),
                        "pre_listing_action": stock.get("pre_listing_action", ""),
                    }
                )
            added_count["new_stock"] += 1
```

Update the emitted summary string to include `新股{added_count['new_stock']}只`.

- [ ] **Step 4: Run the focused tests**

Run:

```bash
python3 -m unittest tests.test_watch_candidates_infer
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

Run:

```bash
git add scripts/domains/watch_candidates/infer.py tests/test_watch_candidates_infer.py
git commit -m "feat: append qualified new stock upgrades"
```

---

### Task 4: Wire New-Stock Side Channel Into Input Runtime

**Files:**
- Modify: `scripts/input/runtime.py`
- Modify: `tests/test_input_runtime.py`

- [ ] **Step 1: Write the failing runtime test**

Add this method to `InputRuntimeTest` in `tests/test_input_runtime.py`:

```python
    def test_run_input_runtime_body_exposes_new_stock_side_channel_when_helpers_are_injected(self):
        input_runtime = importlib.import_module("input.runtime")

        class Timer:
            def start(self):
                return None

            def record(self, *args):
                return (0.01, None)

        def fake_market_state(*args, **kwargs):
            return {
                "results": {
                    "market_research_snapshot": {"state_machine": {"leading_line": "电池"}},
                    "current_mainline_history_record": {"primary_mainline": "电池"},
                },
                "data_status": {},
                "step_status": {},
                "module_logs": [],
            }

        helpers = {
            "StepTimer": Timer,
            "AShareDataCollector": lambda: type("Collector", (), {"get_wanzhu_top10": lambda self, target_date: []})(),
            "TencentFinanceData": lambda: type("Tencent", (), {"get_calendar_events": lambda self, target_date=None: []})(),
            "build_input_request_registry": lambda globals_map: {},
            "resolve_request_target_date": lambda target_date: target_date,
            "collect_market_state_request_bundle": fake_market_state,
            "collect_market_activity_pool_request_bundle": lambda *args, **kwargs: {"results": {}, "data_status": {}, "step_status": {}, "module_logs": [], "artifacts": {}},
            "collect_market_activity_hot_rank_request_bundle": lambda *args, **kwargs: {"results": {}, "data_status": {}, "step_status": {}, "module_logs": []},
            "collect_market_activity_sector_snapshot_request_bundle": lambda *args, **kwargs: {"results": {}, "data_status": {}, "step_status": {}, "module_logs": []},
            "collect_calendar_events_request_bundle": lambda *args, **kwargs: {"results": {}, "data_status": {}, "step_status": {}, "module_logs": []},
            "collect_monitoring_request_bundle": lambda *args, **kwargs: {"results": {}, "data_status": {}, "step_status": {}, "module_logs": []},
            "collect_market_activity_capital_snapshot_request_bundle": lambda *args, **kwargs: {"results": {}, "data_status": {}, "step_status": {}, "module_logs": []},
            "collect_new_stock_calendar_request_bundle": lambda *args, **kwargs: {
                "results": {"new_stock_calendar": [{"code": "301608", "name": "理奇智能", "listing_window": "tomorrow_listing"}]},
                "data_status": {"新股上市日历": True},
                "step_status": {"新股上市日历获取": True},
                "module_logs": [{"module": "domains.new_stock_calendar.request", "step": "request.new_stock_calendar", "status": "success"}],
            },
            "build_new_stock_research_pool": lambda new_stock_calendar=None, target_date="", context=None: {
                "new_stock_research_pool": [{"code": "301608", "name": "理奇智能", "upgrade_eligible": True}],
                "new_stock_candidate_upgrades": [{"code": "301608", "name": "理奇智能", "_source": "新股研究池", "turnover": 1}],
            },
            "build_watch_candidate_pool_bundle": lambda all_data, emit: {
                "results": {"candidates": all_data.get("new_stock_candidate_upgrades", []), "added_count": {"new_stock": 1}},
                "module_logs": [],
            },
            "collect_watch_candidate_history_request_bundle": lambda *args, **kwargs: {"results": {}, "data_status": {}, "step_status": {}, "module_logs": []},
            "build_market_activity_sector_analysis_bundle": lambda *args, **kwargs: {"results": {}, "module_logs": []},
            "build_market_activity_quant_signal_bundle": lambda *args, **kwargs: {"results": {}, "module_logs": []},
            "print": lambda *args, **kwargs: None,
            "get_limit_up_pool": lambda *args, **kwargs: (type("Empty", (), {"empty": True, "to_dict": lambda self, orient: []})(), set()),
            "get_limit_down_pool": lambda *args, **kwargs: (type("Empty", (), {"empty": True, "to_dict": lambda self, orient: []})(), set()),
            "fetch_ths_hot_stock": lambda *args, **kwargs: [],
            "get_integrated_hot_list": lambda *args, **kwargs: {},
            "fetch_hot_plate": lambda *args, **kwargs: [],
            "get_sector_change_from_iwencai": lambda *args, **kwargs: [],
            "get_turnover_rank_from_iwencai": lambda *args, **kwargs: [],
            "XuangubaoIntradayAnalyzer": object,
            "get_lhb": lambda *args, **kwargs: [],
        }

        result = input_runtime.run_input_runtime("2026-04-29", helpers=helpers)

        self.assertEqual(result["new_stock_calendar"][0]["code"], "301608")
        self.assertTrue(result["new_stock_research_pool"][0]["upgrade_eligible"])
        self.assertEqual(result["new_stock_candidate_upgrades"][0]["_source"], "新股研究池")
        self.assertEqual(result["candidates"][0]["code"], "301608")
```

- [ ] **Step 2: Run the runtime test and verify it fails**

Run:

```bash
python3 -m unittest tests.test_input_runtime
```

Expected: FAIL because `input.runtime` has not imported or called the new-stock request/scoring path.

- [ ] **Step 3: Import the new modules**

In `scripts/input/runtime.py`, add:

```python
from domains.new_stock_calendar.request import collect_new_stock_calendar_request_bundle, fetch_sina_new_stock_calendar_pages
from selection.new_stock_narrative_runtime import build_new_stock_research_pool
```

- [ ] **Step 4: Wire the request and scoring before watch candidates are built**

In `_run_input_runtime_legacy_body`, after `calendar_events_result` is merged and before monitoring/candidate construction, add:

```python
        new_stock_calendar_result = collect_new_stock_calendar_request_bundle(
            target_date,
            fetch_pages=fetch_sina_new_stock_calendar_pages,
            timer=timer,
            emit=lambda message: print(message, flush=True),
        )
        results.update(new_stock_calendar_result.get("results", {}))
        data_status.update(new_stock_calendar_result.get("data_status", {}))
        step_status.update(new_stock_calendar_result.get("step_status", {}))
        module_logs.extend(new_stock_calendar_result.get("module_logs", []))

        state_machine = ((results.get("market_research_snapshot") or {}).get("state_machine") or {})
        current_mainline_record = results.get("current_mainline_history_record") or {}
        new_stock_context = {
            "mainline_name": current_mainline_record.get("primary_mainline") or state_machine.get("leading_line") or "",
            "potential_mainlines": state_machine.get("mainline_candidates", []) or [],
            "recent_new_stock_money_effect": results.get("recent_new_stock_money_effect", ""),
            "risk_appetite": state_machine.get("execution_bias", ""),
            "sector_resonance": results.get("sector_resonance", {}) or {},
        }
        new_stock_research = build_new_stock_research_pool(
            results.get("new_stock_calendar", []),
            target_date=target_date,
            context=new_stock_context,
        )
        results.update(new_stock_research)
```

Make sure this block runs before `build_watch_candidate_pool_bundle(results, ...)` so upgrades are available to the candidate builder.

- [ ] **Step 5: Run the focused tests**

Run:

```bash
python3 -m unittest tests.test_input_runtime tests.test_new_stock_calendar_request tests.test_new_stock_narrative_runtime tests.test_watch_candidates_infer
```

Expected: PASS.

- [ ] **Step 6: Commit Task 4**

Run:

```bash
git add scripts/input/runtime.py tests/test_input_runtime.py
git commit -m "feat: wire new stock research into input runtime"
```

---

## Final Verification

- [ ] Run the focused suite:

```bash
python3 -m unittest \
  tests.test_new_stock_calendar_request \
  tests.test_new_stock_narrative_runtime \
  tests.test_watch_candidates_infer \
  tests.test_input_runtime \
  tests.test_candidate_bundle_runtime \
  tests.test_special_probe_runtime
```

Expected: PASS.

- [ ] Run diff hygiene:

```bash
git diff --check
```

Expected: no output.

## Plan Self-Review

- Spec coverage: Task 1 covers official listing-date source; Task 2 covers research scoring, T-2/T-1 actions, and calibration; Task 3 covers upgrade-only candidate integration; Task 4 covers input runtime exposure.
- Red-flag scan: every task has concrete tests, file paths, commands, and implementation snippets.
- Type consistency: shared fields are `new_stock_calendar`, `new_stock_research_pool`, `new_stock_candidate_upgrades`, `listing_window`, `pre_listing_action`, `new_stock_narrative_score`, and `new_stock_factors`.
