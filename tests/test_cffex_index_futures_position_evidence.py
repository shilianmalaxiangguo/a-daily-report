import datetime as dt
import sys
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from market_data.cffex_index_futures import (  # noqa: E402
    CFFEX_CONTRACT_MULTIPLIERS,
    CFFEX_PRODUCTS,
    CFFEX_SOURCE_POLICY,
)
from report.cffex_index_futures_position_evidence import (  # noqa: E402
    align_cffex_history_calendar,
    build_cffex_index_futures_position_evidence,
    build_unavailable_cffex_evidence,
    canonical_cffex_evidence_hash,
    load_cffex_index_futures_position_evidence,
    render_cffex_evidence_lines,
    validate_cffex_evidence,
)
from report.runtime import _attach_cffex_index_futures_position_evidence  # noqa: E402


TARGET = "2026-08-19"
CONTENT_HASH = "a" * 64
MEMBER_VALUES = {
    "IF": (33040, 51549, 3126, 3636),
    "IH": (13743, 25877, 965, 1449),
    "IC": (50970, 62299, 3332, 3546),
    "IM": (70790, 97451, 7738, 9660),
}
TOP20_VALUES = {
    "IF": (212087, 239093, 15789, 17208, 23999),
    "IH": (89614, 107703, 8694, 9757, 17145),
    "IC": (236933, 260657, 17083, 15178, 23812),
    "IM": (346088, 396471, 31321, 31464, 49666),
}


class _NonPostgresService:
    def __init__(self):
        self.calls = 0

    def is_postgres_backed(self):
        return False

    def query_cffex_index_futures_day(self, _target):
        self.calls += 1
        raise AssertionError("replay must not query a non-PostgreSQL service")


class _WritingService:
    def is_postgres_backed(self):
        return True

    def query_cffex_index_futures_day(self, _target):
        return {}

    def query_cffex_index_futures_history(self, _target, *, window_days=60):
        return {}

    def query_index_daily_bars(self, *_args, **_kwargs):
        return []

    def replace_cffex_index_futures_day(self, *_args, **_kwargs):
        raise RuntimeError("database unavailable")


class CffexIndexFuturesPositionEvidenceTest(unittest.TestCase):
    def test_calendar_alignment_preserves_gap_and_rejects_resigned_wrong_dates(self):
        payload = build_cffex_index_futures_position_evidence(TARGET, _complete_day(TARGET))
        original = deepcopy(payload)
        calendar = ['2026-08-18', TARGET]
        revised = align_cffex_history_calendar(payload, calendar, calendar_source='test.open_dates')
        self.assertEqual(payload, original)
        self.assertEqual(revised['history']['sample_count'], 1)
        for windows in revised['history']['windows'].values():
            self.assertIsNone(windows['60']['values'][0]['value'])
            self.assertEqual(windows['60']['values'][0]['trade_date'], calendar[0])
        self.assertEqual(validate_cffex_evidence(revised, target_date=TARGET), (True, []))
        metric = revised['history']['windows']['member_net_short_change']['60']
        metric['values'][0]['trade_date'] = '2026-08-17'
        revised['artifact_hash'] = canonical_cffex_evidence_hash(revised)
        self.assertFalse(validate_cffex_evidence(revised, target_date=TARGET)[0])

    def test_calendar_alignment_retains_missing_target_as_null(self):
        payload = build_unavailable_cffex_evidence(TARGET, reason='当日来源未返回')
        revised = align_cffex_history_calendar(payload, ['2026-08-18', TARGET],
                                               calendar_source='test.open_dates')
        self.assertEqual(revised['history']['sample_count'], 0)
        self.assertEqual(validate_cffex_evidence(revised, target_date=TARGET), (True, []))
        for windows in revised['history']['windows'].values():
            self.assertTrue(windows['60']['target_date_present'])
            self.assertIsNone(windows['60']['current_value'])
            self.assertTrue(all(r['value'] is None for r in windows['60']['values']))

    def test_calendar_alignment_keeps_exact_sixty_sessions_and_twenty_subset(self):
        dates = [(dt.date.fromisoformat(TARGET) - dt.timedelta(days=i)).isoformat()
                 for i in range(59, -1, -1)]
        summaries = [{'trade_date': day, 'complete_scope': True, 'member_net_short_change': i,
                      'member_net_short_notional': i * 100, 'top20_cross_section_net_short': i * 10}
                     for i, day in enumerate(dates)]
        payload = build_cffex_index_futures_position_evidence(
            TARGET, _complete_day(TARGET), {'summaries': summaries})
        revised = align_cffex_history_calendar(payload, dates, calendar_source='test.open_dates')
        self.assertEqual(revised['history']['coverage_status'], 'complete')
        self.assertEqual(revised['history']['sample_count'], 60)
        for windows in revised['history']['windows'].values():
            self.assertEqual([r['trade_date'] for r in windows['60']['values']], dates)
            self.assertEqual(windows['20']['values'], windows['60']['values'][-20:])
        self.assertEqual(validate_cffex_evidence(revised, target_date=TARGET), (True, []))

    def test_aligned_evidence_replaces_stale_chart_and_explains_actual_coverage(self):
        from bs4 import BeautifulSoup
        from report.sector_daily_report import render_sector_daily
        from report.sector_snapshot_charts import snapshot_chart_payload
        payload = build_cffex_index_futures_position_evidence(TARGET, _complete_day(TARGET))
        payload = align_cffex_history_calendar(payload, ['2026-08-18', TARGET], calendar_source='test.open_dates')
        data = {'cffex_index_futures_position_evidence': payload,
                'reading_chart_payload': {'cffex_position_trend': {'items': [{'date': '2026-01-01'}]}}}
        original = deepcopy(data)
        chart = snapshot_chart_payload(data, TARGET)['cffex_position_trend']
        self.assertEqual([r['date'] for r in chart['items']], ['2026-08-18', TARGET])
        self.assertEqual(chart['complete_day_count'], 1)
        page = BeautifulSoup(render_sector_daily(None, TARGET, snapshot={'date': TARGET, 'data': data}), 'html.parser')
        self.assertIn('三项事实齐全1/2日', page.get_text())
        self.assertEqual(data, original)

    def test_calendar_alignment_never_compares_to_an_older_recorded_session(self):
        current = _complete_day(TARGET)
        for day in ('2026-08-17', '2026-08-18'):
            with self.subTest(day=day):
                prior = _complete_day(day, previous=True)
                payload = build_cffex_index_futures_position_evidence(TARGET, current,
                    {'contract_rows': prior['contract_rows'] + current['contract_rows'],
                     'member_rank_rows': prior['member_rank_rows'] + current['member_rank_rows']})
                self.assertEqual(payload['top20']['overall']['previous_trade_date'], day)
                value = align_cffex_history_calendar(payload, ['2026-08-17', '2026-08-18', TARGET],
                                                     calendar_source='test.open_dates')
                for item in [value['top20']['overall'], *value['top20']['products'].values()]:
                    if day == '2026-08-17':
                        for key in ('previous_trade_date', 'previous_top20_cross_section_net_short',
                                    'top20_cross_section_change', 'membership_scope_residual', 'membership_changes'):
                            self.assertIsNone(item[key])
                        self.assertEqual(item['comparison_availability'], 'incomplete')
                    else:
                        self.assertEqual(item['previous_trade_date'], day)
                        self.assertIsNotNone(item['previous_top20_cross_section_net_short'])
                self.assertEqual(validate_cffex_evidence(value, target_date=TARGET), (True, []))
                value['top20']['overall']['previous_trade_date'] = '2026-08-17'
                value['artifact_hash'] = canonical_cffex_evidence_hash(value)
                self.assertFalse(validate_cffex_evidence(value, target_date=TARGET)[0])

    def test_unavailable_aligned_source_removes_previous_futures_chart(self):
        from report.sector_snapshot_charts import snapshot_chart_payload
        valid = build_cffex_index_futures_position_evidence(TARGET, _complete_day(TARGET))
        old = snapshot_chart_payload({'cffex_index_futures_position_evidence': valid}, TARGET)
        missing = align_cffex_history_calendar(build_unavailable_cffex_evidence(TARGET, reason='来源未返回'),
            ['2026-08-18', TARGET], calendar_source='test.open_dates')
        original = deepcopy(old)
        result = snapshot_chart_payload({'reading_chart_payload': old,
                                        'cffex_index_futures_position_evidence': missing}, TARGET)
        self.assertNotIn('cffex_position_trend', result)
        self.assertEqual(old, original)

    def test_reference_values_hash_and_rendered_context(self):
        current = _complete_day(TARGET)
        previous_date = "2026-08-18"
        previous = _complete_day(previous_date, previous=True)

        payload = build_cffex_index_futures_position_evidence(
            TARGET,
            current,
            {
                "contract_rows": previous["contract_rows"] + current["contract_rows"],
                "member_rank_rows": previous["member_rank_rows"] + current["member_rank_rows"],
            },
            spot_rows_by_product={
                product: {"trade_date": TARGET, "close": 99.0}
                for product in CFFEX_PRODUCTS
            },
            query_date="2026-08-20",
        )

        overall = payload["member_position"]["overall"]
        top20 = payload["top20"]["overall"]
        self.assertEqual(payload["availability"], "complete")
        self.assertEqual(overall["long_daily_change"], 15161)
        self.assertEqual(overall["short_daily_change"], 18291)
        self.assertEqual(overall["net_short_change"], 3130)
        self.assertEqual(top20["top20_cross_section_net_short"], 119202)
        self.assertEqual(top20["top20_cross_section_change"], 4580)
        self.assertEqual(top20["listed_member_daily_change_net"], 720)
        self.assertEqual(top20["membership_scope_residual"], 3860)
        self.assertEqual(payload["artifact_hash"], canonical_cffex_evidence_hash(payload))
        self.assertEqual(validate_cffex_evidence(payload, target_date=TARGET), (True, []))

        markdown = "\n".join(render_cffex_evidence_lines(payload))
        self.assertIn("3,130", markdown)
        self.assertIn("119,202", markdown)
        self.assertIn("全市场持仓变化", markdown)
        self.assertIn("近月基差", markdown)
        self.assertIn("20日", markdown)
        self.assertIn("60日", markdown)

    def test_unavailable_payload_renders_only_explicit_fact_shortage(self):
        payload = build_unavailable_cffex_evidence(
            TARGET,
            reason="目标日 PostgreSQL 中金所事实缺失",
            query_date="2026-08-20",
        )

        self.assertEqual(validate_cffex_evidence(payload, target_date=TARGET), (True, []))
        markdown = "\n".join(render_cffex_evidence_lines(payload))
        self.assertIn("事实不足，不把当前来源或其他日期替代目标日", markdown)
        self.assertNotIn("多头持仓(手)", markdown)

    def test_incomplete_rank_numbers_cannot_be_reported_complete(self):
        day = _complete_day(TARGET)
        day["member_rank_rows"] = [
            row for row in day["member_rank_rows"] if row["rank_no"] == 1
        ]

        payload = build_cffex_index_futures_position_evidence(TARGET, day)

        self.assertEqual(payload["availability"], "partial")
        self.assertTrue(
            any("排名不是1-20连续名次" in reason for reason in payload["missing_reasons"])
        )

    def test_single_product_history_never_claims_sixty_day_coverage(self):
        contracts = []
        ranks = []
        end = dt.date.fromisoformat(TARGET)
        for offset in range(59, -1, -1):
            trade_date = (end - dt.timedelta(days=offset)).isoformat()
            day = _complete_day(trade_date, products=("IF",))
            contracts.extend(day["contract_rows"])
            ranks.extend(day["member_rank_rows"])
        current = _complete_day(TARGET)

        payload = build_cffex_index_futures_position_evidence(
            TARGET,
            current,
            {"contract_rows": contracts, "member_rank_rows": ranks},
        )

        self.assertEqual(payload["history"]["coverage_status"], "partial")
        self.assertEqual(
            payload["history"]["windows"]["top20_cross_section_net_short"]["60"]["coverage_status"],
            "insufficient",
        )

    def test_frozen_payload_rejects_nested_wrong_source_date_after_rehash(self):
        payload = build_cffex_index_futures_position_evidence(
            TARGET,
            _complete_day(TARGET),
            query_date="2026-08-20",
        )
        tampered = deepcopy(payload)
        tampered["raw_target_day"]["contract_rows"][0]["source_date"] = "2026-08-18"
        tampered["artifact_hash"] = canonical_cffex_evidence_hash(tampered)

        valid, errors = validate_cffex_evidence(tampered, target_date=TARGET)

        self.assertFalse(valid)
        self.assertIn("cffex_evidence_contract_rows_invalid", errors)

    def test_selected_member_missing_one_side_marks_payload_partial(self):
        day = _complete_day(TARGET)
        missing_row = next(
            row
            for row in day["member_rank_rows"]
            if row["product_code"] == "IM"
            and row["rank_type"] == "short"
            and row["rank_no"] == 1
        )
        missing_row["member_name"] = "其他会员(代客)"

        payload = build_cffex_index_futures_position_evidence(TARGET, day)

        self.assertEqual(payload["availability"], "partial")
        self.assertEqual(payload["products"]["IM"]["availability"], "partial")
        self.assertEqual(
            payload["products"]["IM"]["member_position"]["availability"],
            "unavailable",
        )
        self.assertEqual(validate_cffex_evidence(payload, target_date=TARGET), (True, []))
        markdown = "\n".join(render_cffex_evidence_lines(payload))
        self.assertIn("覆盖状态：部分", markdown)
        self.assertIn("中信期货short披露行数量为0", markdown)

    def test_frozen_payload_rejects_tampered_product_copy_after_rehash(self):
        payload = build_cffex_index_futures_position_evidence(
            TARGET,
            _complete_day(TARGET),
            query_date="2026-08-20",
        )
        tampered = deepcopy(payload)
        tampered["products"]["IF"]["contract_rows"][0]["source_date"] = "2026-08-20"
        tampered["artifact_hash"] = canonical_cffex_evidence_hash(tampered)

        valid, errors = validate_cffex_evidence(tampered, target_date=TARGET)

        self.assertFalse(valid)
        self.assertIn("cffex_evidence_product_rows_invalid:IF", errors)
        self.assertIn("cffex_evidence_product_contract_rows_mismatch:IF", errors)

    def test_frozen_payload_rejects_future_history_after_rehash(self):
        payload = build_cffex_index_futures_position_evidence(
            TARGET,
            _complete_day(TARGET),
            query_date="2026-08-20",
        )
        tampered = deepcopy(payload)
        tampered["history"]["trade_dates"][-1] = "2026-08-21"
        tampered["history"]["end_date"] = "2026-08-21"
        tampered["artifact_hash"] = canonical_cffex_evidence_hash(tampered)

        valid, errors = validate_cffex_evidence(tampered, target_date=TARGET)

        self.assertFalse(valid)
        self.assertIn("cffex_evidence_history_future_or_invalid_date", errors)

    def test_frozen_payload_rejects_tampered_member_derivation_after_rehash(self):
        payload = build_cffex_index_futures_position_evidence(
            TARGET,
            _complete_day(TARGET),
            query_date="2026-08-20",
        )
        tampered = deepcopy(payload)
        tampered["member_position"]["overall"]["net_short_change"] = 999999
        tampered["artifact_hash"] = canonical_cffex_evidence_hash(tampered)

        valid, errors = validate_cffex_evidence(tampered, target_date=TARGET)

        self.assertFalse(valid)
        self.assertIn("cffex_evidence_member_projection_mismatch", errors)

    def test_frozen_payload_rejects_missing_explicit_provenance_after_rehash(self):
        payload = build_cffex_index_futures_position_evidence(
            TARGET,
            _complete_day(TARGET),
            query_date="2026-08-20",
        )
        tampered = deepcopy(payload)
        tampered["raw_target_day"]["member_rank_rows"][0].pop("query_date")
        tampered["raw_target_day"]["member_rank_rows"][1].pop("source_policy")
        tampered["artifact_hash"] = canonical_cffex_evidence_hash(tampered)

        valid, errors = validate_cffex_evidence(tampered, target_date=TARGET)

        self.assertFalse(valid)
        self.assertIn("cffex_evidence_rank_rows_invalid", errors)

    def test_frozen_payload_rejects_duplicate_rank_key_after_rehash(self):
        day = _complete_day(TARGET)
        day["member_rank_rows"].append(deepcopy(day["member_rank_rows"][0]))
        payload = build_cffex_index_futures_position_evidence(TARGET, day)

        valid, errors = validate_cffex_evidence(payload, target_date=TARGET)

        self.assertEqual(payload["availability"], "partial")
        self.assertFalse(valid)
        self.assertIn("cffex_evidence_raw_scope_invalid", errors)

    def test_contract_scope_change_lowers_cross_day_comparability(self):
        current = _complete_day(TARGET)
        for row in [*current["contract_rows"], *current["member_rank_rows"]]:
            row["contract_code"] = row["contract_code"].replace("2608", "2609")
        previous = _complete_day("2026-08-18", previous=True)

        payload = build_cffex_index_futures_position_evidence(
            TARGET,
            current,
            {
                "contract_rows": previous["contract_rows"] + current["contract_rows"],
                "member_rank_rows": previous["member_rank_rows"]
                + current["member_rank_rows"],
            },
        )

        comparison = payload["top20"]["overall"]
        self.assertEqual(comparison["comparison_availability"], "incomplete")
        self.assertEqual(
            comparison["membership_changes"]["contracts_entered"],
            ["IC2609", "IF2609", "IH2609", "IM2609"],
        )
        self.assertEqual(validate_cffex_evidence(payload, target_date=TARGET), (True, []))

    def test_replay_does_not_query_non_postgres_service(self):
        service = _NonPostgresService()

        payload = load_cffex_index_futures_position_evidence(
            TARGET,
            service=service,
            replay=True,
            query_date="2026-08-20",
        )

        self.assertEqual(service.calls, 0)
        self.assertEqual(payload["availability"], "unavailable")

    def test_replay_missing_fact_never_calls_collector_or_writer(self):
        calls = {"collector": 0, "writer": 0}

        class ReadOnlyService:
            def is_postgres_backed(self):
                return True

            def query_cffex_index_futures_day(self, _target):
                return {}

            def query_index_daily_bars(self, *_args, **_kwargs):
                return []

            def replace_cffex_index_futures_day(self, *_args, **_kwargs):
                calls["writer"] += 1
                raise AssertionError("replay must not write")

        def collector(*_args, **_kwargs):
            calls["collector"] += 1
            raise AssertionError("replay must not collect")

        payload = load_cffex_index_futures_position_evidence(
            TARGET,
            service=ReadOnlyService(),
            replay=True,
            collector=collector,
            query_date="2026-08-20",
            allow_fresh_write=False,
        )

        self.assertEqual(payload["availability"], "unavailable")
        self.assertEqual(calls, {"collector": 0, "writer": 0})

    def test_fresh_write_failure_degrades_optional_evidence(self):
        current = _complete_day(TARGET)

        payload = load_cffex_index_futures_position_evidence(
            TARGET,
            service=_WritingService(),
            collector=lambda *_args, **_kwargs: current,
            query_date="2026-08-20",
        )

        self.assertEqual(payload["availability"], "unavailable")
        self.assertIn("保存失败", payload["missing_reasons"][0])

    def test_fresh_read_only_collection_keeps_local_history_and_current_point(self):
        current = _complete_day(TARGET)
        previous = _complete_day('2026-08-18', previous=True)

        class Service(_WritingService):
            def query_cffex_index_futures_history(self, _target, *, window_days=60):
                return {'contract_rows': previous['contract_rows'], 'member_rank_rows': previous['member_rank_rows']}

        payload = load_cffex_index_futures_position_evidence(
            TARGET, service=Service(), collector=lambda *a, **k: current,
            query_date='2026-08-20', allow_fresh_write=False)
        self.assertEqual(payload['availability'], 'complete')
        self.assertEqual(payload['history']['trade_dates'], ['2026-08-18', TARGET])
        self.assertEqual(payload['history']['windows']['member_net_short_change']['60']['values'][-1]['trade_date'], TARGET)
        self.assertEqual(validate_cffex_evidence(payload, target_date=TARGET), (True, []))

    def test_read_only_history_failure_keeps_target_and_reports_the_gap(self):
        current = _complete_day(TARGET)

        class Service(_WritingService):
            def query_cffex_index_futures_history(self, _target, *, window_days=60):
                raise RuntimeError('历史来源暂不可用')

        payload = load_cffex_index_futures_position_evidence(
            TARGET, service=Service(), collector=lambda *a, **k: current,
            query_date='2026-08-20', allow_fresh_write=False)
        self.assertEqual(payload['availability'], 'complete')
        self.assertEqual(payload['history']['trade_dates'], [TARGET])
        self.assertIn('历史窗口读取失败', '；'.join(payload['missing_reasons']))
        self.assertIn('仅保留目标日', '\n'.join(render_cffex_evidence_lines(payload)))
        self.assertEqual(validate_cffex_evidence(payload, target_date=TARGET), (True, []))

    def test_loader_uses_compact_sixty_day_summaries_and_two_day_comparison(self):
        current = _complete_day(TARGET)
        previous = _complete_day("2026-08-18", previous=True)

        class SummaryService:
            def __init__(self):
                self.summary_windows = []
                self.history_windows = []

            def is_postgres_backed(self):
                return True

            def query_cffex_index_futures_day(self, _target):
                return current

            def query_cffex_index_futures_history_summaries(
                self, _target, *, window_days=60
            ):
                self.summary_windows.append(window_days)
                end = dt.date.fromisoformat(TARGET)
                return {
                    "summaries": [
                        {
                            "trade_date": (end - dt.timedelta(days=59 - offset)).isoformat(),
                            "member_net_short_change": 3000 + offset,
                            "member_net_short_notional": 1_000_000_000 + offset,
                            "top20_cross_section_net_short": 110_000 + offset,
                            "complete_scope": True,
                        }
                        for offset in range(60)
                    ],
                    "source": "postgresql.cffex_index_futures.summary",
                }

            def query_cffex_index_futures_history(self, _target, *, window_days=60):
                self.history_windows.append(window_days)
                return {
                    "contract_rows": previous["contract_rows"] + current["contract_rows"],
                    "member_rank_rows": previous["member_rank_rows"]
                    + current["member_rank_rows"],
                }

            def query_index_daily_bars(self, *_args, **_kwargs):
                return []

        service = SummaryService()

        payload = load_cffex_index_futures_position_evidence(
            TARGET,
            service=service,
            replay=True,
            query_date="2026-08-20",
        )

        self.assertEqual(service.summary_windows, [60])
        self.assertEqual(service.history_windows, [2])
        self.assertEqual(payload["history"]["sample_count"], 60)
        self.assertEqual(
            payload["history"]["windows"]["member_net_short_change"]["60"][
                "coverage_status"
            ],
            "complete",
        )
        self.assertEqual(payload["member_position"]["overall"]["net_short_change"], 3130)
        self.assertEqual(payload["top20"]["overall"]["top20_cross_section_change"], 4580)
        self.assertEqual(payload["top20"]["overall"]["listed_member_daily_change_net"], 720)
        self.assertEqual(payload["top20"]["overall"]["membership_scope_residual"], 3860)

    def test_runtime_inserts_after_action_without_changing_formal_decision(self):
        payload = build_cffex_index_futures_position_evidence(
            TARGET,
            _complete_day(TARGET),
            query_date="2026-08-20",
        )
        data = {
            "selection_workflow": {"final": {"code": "600667"}},
            "final_target_resolution": {
                "new_entry_target": {"code": "600667", "name": "太极实业"},
                "position_pct": 50,
                "execution_nature": "50%条件执行",
            },
            "position_decision": {"position_pct": 50},
        }
        formal_before = deepcopy(data)
        report = "\n".join(
            [
                "## 明日执行结论",
                "### 账户动作",
                "按既定条件执行。",
                "",
                "## 市场语言翻译（研究证据）",
                "研究正文。",
            ]
        )

        rendered, artifact, review = _attach_cffex_index_futures_position_evidence(
            report,
            data,
            target_date=TARGET,
            run_mode="replay",
            source_payload=payload,
        )

        self.assertLess(rendered.index("## 明日执行结论"), rendered.index("## 股指期货持仓结构（研究证据）"))
        self.assertLess(rendered.index("## 股指期货持仓结构（研究证据）"), rendered.index("## 市场语言翻译（研究证据）"))
        for key, value in formal_before.items():
            self.assertEqual(data[key], value)
        self.assertEqual(artifact["artifact_hash"], payload["artifact_hash"])
        self.assertTrue(review["unchanged"])


def _complete_day(trade_date, *, previous=False, products=CFFEX_PRODUCTS):
    contracts = [_contract_row(product, trade_date) for product in products]
    ranks = []
    for product in products:
        ranks.extend(_rank_rows(product, trade_date, previous=previous))
    return {
        "trade_date": trade_date,
        "availability": "complete",
        "contract_rows": contracts,
        "member_rank_rows": ranks,
        "source_errors": [],
    }


def _contract_row(product, trade_date):
    return {
        "trade_date": trade_date,
        "source_date": trade_date,
        "query_date": "2026-08-20",
        "product_code": product,
        "contract_code": f"{product}2608",
        "close_price": 100.0,
        "settlement_price": 100.0,
        "previous_settlement_price": 99.0,
        "volume": 1000,
        "open_interest": 1100,
        "previous_open_interest": 1000,
        "contract_multiplier": CFFEX_CONTRACT_MULTIPLIERS[product],
        "source_url": f"http://example.test/{trade_date}/index.xml",
        "content_hash": CONTENT_HASH,
        "source_policy": CFFEX_SOURCE_POLICY,
    }


def _rank_rows(product, trade_date, *, previous=False):
    current_long, current_short, long_change, short_change, previous_net = TOP20_VALUES[product]
    if previous:
        long_total = current_long
        short_total = current_long + previous_net
        long_change = 0
        short_change = 0
    else:
        long_total = current_long
        short_total = current_short
    member_long, member_short, member_long_change, member_short_change = MEMBER_VALUES[product]
    contract = f"{product}2608"
    rows = []
    for rank_type in ("volume", "long", "short"):
        for rank_no in range(1, 21):
            if rank_type == "long":
                quantity = member_long if rank_no == 1 else (long_total - member_long if rank_no == 2 else 0)
                daily_change = member_long_change if rank_no == 1 else (long_change - member_long_change if rank_no == 2 else 0)
            elif rank_type == "short":
                quantity = member_short if rank_no == 1 else (short_total - member_short if rank_no == 2 else 0)
                daily_change = member_short_change if rank_no == 1 else (short_change - member_short_change if rank_no == 2 else 0)
            else:
                quantity = 1000 - rank_no
                daily_change = None
            rows.append(
                {
                    "trade_date": trade_date,
                    "source_date": trade_date,
                    "query_date": "2026-08-20",
                    "product_code": product,
                    "contract_code": contract,
                    "rank_type": rank_type,
                    "rank_no": rank_no,
                    "member_id": f"{rank_no:04d}",
                    "member_name": "中信期货(代客)" if rank_no == 1 else f"会员{rank_no}",
                    "quantity": quantity,
                    "daily_change": daily_change,
                    "source_url": f"http://example.test/{trade_date}/{product}.xml",
                    "content_hash": CONTENT_HASH,
                    "source_policy": CFFEX_SOURCE_POLICY,
                }
            )
    return rows


if __name__ == "__main__":
    unittest.main()
