import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from market_data.cffex_index_futures import (  # noqa: E402
    CFFEX_CONTRACT_MULTIPLIERS,
    CffexDataError,
    build_contract_market_context,
    build_history_windows,
    build_member_position_summary,
    build_top20_structure,
    parse_contract_daily_xml,
    parse_member_rank_xml,
)


FIXTURE_DIR = ROOT / "tests" / "fixtures" / "cffex_index_futures"


class CffexIndexFuturesPositionTest(unittest.TestCase):
    def test_parses_official_member_rank_shape_and_preserves_provenance(self):
        raw = (FIXTURE_DIR / "member_rank_sample.xml").read_bytes()

        rows = parse_member_rank_xml(
            raw,
            expected_trade_date="2026-08-19",
            expected_product="IF",
            source_url="http://example.test/IF.xml",
            query_date="2026-08-19",
            expected_rank_count=1,
        )

        self.assertEqual([row["rank_type"] for row in rows], ["long", "short", "volume"])
        long_row = rows[0]
        self.assertEqual(long_row["contract_code"], "IF2608")
        self.assertEqual(long_row["member_name"], "中信期货(代客)")
        self.assertEqual(long_row["member_id"], "0018")
        self.assertEqual(long_row["quantity"], 4670)
        self.assertEqual(long_row["daily_change"], -232)
        self.assertEqual(long_row["source_date"], "2026-08-19")
        self.assertEqual(long_row["query_date"], "2026-08-19")
        self.assertEqual(len(long_row["content_hash"]), 64)

    def test_member_rank_rejects_wrong_date_duplicate_rank_and_missing_type(self):
        raw = (FIXTURE_DIR / "member_rank_sample.xml").read_bytes()
        with self.assertRaisesRegex(CffexDataError, "目标日期"):
            parse_member_rank_xml(
                raw,
                expected_trade_date="2026-08-18",
                expected_product="IF",
                query_date="2026-08-19",
                expected_rank_count=1,
            )

        duplicate = raw.replace(b"</positionRank>", raw.split(b"<data>", 1)[1].split(b"</data>", 1)[0].join([b"<data>", b"</data></positionRank>"]))
        with self.assertRaises(CffexDataError):
            parse_member_rank_xml(
                duplicate,
                expected_trade_date="2026-08-19",
                expected_product="IF",
                query_date="2026-08-19",
                expected_rank_count=1,
            )

        missing_short = raw.replace(
            b"  <data><instrumentid>IF2608</instrumentid><tradingday>20260819</tradingday><datatypeid>2</datatypeid><rank>1</rank><shortname>\xe4\xb8\xad\xe4\xbf\xa1\xe6\x9c\x9f\xe8\xb4\xa7(\xe4\xbb\xa3\xe5\xae\xa2)</shortname><volume>4747</volume><varvolume>-66</varvolume><partyid>0018</partyid><productid>IF</productid></data>\n",
            b"",
        )
        with self.assertRaisesRegex(CffexDataError, "缺少排名类型"):
            parse_member_rank_xml(
                missing_short,
                expected_trade_date="2026-08-19",
                expected_product="IF",
                query_date="2026-08-19",
                expected_rank_count=1,
            )

    def test_parses_contract_daily_shape_and_excludes_options(self):
        raw = (FIXTURE_DIR / "contract_daily_sample.xml").read_bytes()

        rows = parse_contract_daily_xml(
            raw,
            expected_trade_date="2026-08-19",
            source_url="http://example.test/index.xml",
            query_date="2026-08-19",
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["contract_code"], "IF2608")
        self.assertEqual(rows[0]["settlement_price"], 4576.6)
        self.assertEqual(rows[0]["open_interest"], 26606)
        self.assertEqual(rows[0]["contract_multiplier"], 300)

    def test_member_formula_covers_add_short_reduce_long_and_both_reduce(self):
        cases = (
            (100, 130, 0, 30, 30),
            (100, 130, -30, 0, 30),
            (100, 130, -40, -10, 30),
            (100, 100, 10, 10, 0),
            (130, 100, 20, -10, -30),
        )
        for long_qty, short_qty, long_change, short_change, expected_change in cases:
            with self.subTest(cases=(long_change, short_change)):
                ranks = _member_rows(
                    "IF",
                    long_qty=long_qty,
                    short_qty=short_qty,
                    long_change=long_change,
                    short_change=short_change,
                )
                result = build_member_position_summary(ranks, [_contract_row("IF")])
                self.assertEqual(result["overall"]["net_short_balance"], short_qty - long_qty)
                self.assertEqual(result["overall"]["long_daily_change"], long_change)
                self.assertEqual(result["overall"]["short_daily_change"], short_change)
                self.assertEqual(result["overall"]["net_short_change"], expected_change)

    def test_member_missing_one_side_is_incomplete_and_never_zero_filled(self):
        ranks = _member_rows("IF", long_qty=100, short_qty=130, long_change=10, short_change=20)
        ranks = [row for row in ranks if row["rank_type"] != "short"]

        result = build_member_position_summary(ranks, [_contract_row("IF")])

        self.assertEqual(result["availability"], "unavailable")
        self.assertEqual(result["overall"]["included_contract_count"], 0)
        self.assertEqual(result["excluded_contracts"][0]["missing"], ["short"])
        for key in (
            "long_quantity",
            "short_quantity",
            "net_short_balance",
            "long_daily_change",
            "short_daily_change",
            "net_short_change",
        ):
            self.assertIsNone(result["overall"][key])

    def test_top20_incomplete_sides_and_empty_previous_do_not_create_false_changes(self):
        current = _top20_rows(
            "IF",
            {
                "current_long": 100,
                "current_short": 130,
                "long_daily_change": 10,
                "short_daily_change": 20,
                "previous_net_short": 0,
            },
            current=True,
        )
        missing_side = [current[0], {**current[1], "contract_code": "IH2608", "product_code": "IH"}]

        incomplete = build_top20_structure(
            missing_side,
            [],
            expected_rank_count=1,
        )["overall"]
        no_previous = build_top20_structure(
            current,
            [],
            expected_rank_count=1,
        )["overall"]

        self.assertEqual(incomplete["availability"], "incomplete")
        self.assertIsNone(incomplete["top20_cross_section_net_short"])
        self.assertIsNone(incomplete["listed_member_daily_change_net"])
        self.assertIsNone(no_previous["previous_top20_cross_section_net_short"])
        self.assertIsNone(no_previous["top20_cross_section_change"])
        self.assertIsNone(no_previous["membership_scope_residual"])

    def test_2026_08_19_reference_reproduces_member_and_top20_values(self):
        fixture = json.loads((FIXTURE_DIR / "2026-08-19-reference.json").read_text(encoding="utf-8"))
        member_rows = []
        contracts = []
        current_top20 = []
        previous_top20 = []
        for product, values in fixture["member_products"].items():
            member_rows.extend(
                _member_rows(
                    product,
                    long_qty=values["long_quantity"],
                    short_qty=values["short_quantity"],
                    long_change=values["long_daily_change"],
                    short_change=values["short_daily_change"],
                )
            )
            contracts.append(_contract_row(product))
            top20 = fixture["top20_products"][product]
            current_top20.extend(_top20_rows(product, top20, current=True))
            previous_top20.extend(_top20_rows(product, top20, current=False))

        member = build_member_position_summary(member_rows, contracts)
        structure = build_top20_structure(
            current_top20,
            previous_top20,
            expected_rank_count=1,
        )["overall"]
        expected = fixture["expected"]

        self.assertEqual(member["overall"]["long_daily_change"], expected["member_long_daily_change"])
        self.assertEqual(member["overall"]["short_daily_change"], expected["member_short_daily_change"])
        self.assertEqual(member["overall"]["net_short_change"], expected["member_net_short_change"])
        self.assertEqual(structure["top20_cross_section_net_short"], expected["top20_net_short_balance"])
        self.assertEqual(structure["top20_cross_section_change"], expected["top20_cross_section_change"])
        self.assertEqual(structure["listed_member_daily_change_net"], expected["listed_member_daily_change_net"])
        self.assertEqual(structure["membership_scope_residual"], expected["membership_scope_residual"])

    def test_notional_uses_each_product_multiplier_and_keeps_hands_separate(self):
        ranks = []
        contracts = []
        for product in ("IF", "IH", "IC", "IM"):
            ranks.extend(_member_rows(product, long_qty=10, short_qty=20, long_change=1, short_change=2))
            contracts.append(_contract_row(product, settlement=100))

        result = build_member_position_summary(ranks, contracts)

        self.assertEqual(result["overall"]["net_short_balance"], 40)
        expected_notional = 10 * 100 * (300 + 300 + 200 + 200)
        self.assertEqual(result["overall"]["net_short_notional"], expected_notional)
        self.assertEqual(result["products"]["IF"]["net_short_notional"], 10 * 100 * 300)
        self.assertEqual(result["products"]["IM"]["net_short_notional"], 10 * 100 * 200)

    def test_market_context_marks_rollover_and_requires_same_date_spot(self):
        front = _contract_row("IF", contract="IF2608", settlement=100, open_interest=80, previous_open_interest=100)
        far = _contract_row("IF", contract="IF2609", settlement=101, open_interest=140, previous_open_interest=100)

        result = build_contract_market_context(
            [front, far],
            spot_rows_by_product={"IF": {"trade_date": "2026-08-19", "close": 99}},
        )

        self.assertEqual(result["products"]["IF"]["rollover_status"], "likely")
        self.assertEqual(result["rows"][0]["basis"], 1)
        stale = build_contract_market_context(
            [front],
            spot_rows_by_product={"IF": {"trade_date": "2026-08-18", "close": 99}},
        )
        self.assertIsNone(stale["rows"][0]["basis"])

    def test_history_windows_exclude_future_and_report_actual_coverage(self):
        rows = [
            {"trade_date": f"2026-08-{day:02d}", "metric": day}
            for day in range(1, 22)
        ]
        rows.append({"trade_date": "2026-08-20", "metric": 999})

        result = build_history_windows(
            rows,
            target_date="2026-08-19",
            value_key="metric",
        )

        self.assertEqual(result["20"]["sample_count"], 19)
        self.assertEqual(result["20"]["end_date"], "2026-08-19")
        self.assertEqual(result["20"]["coverage_status"], "insufficient")
        self.assertEqual(result["20"]["empirical_percentile_pct"], 100)
        self.assertEqual(result["60"]["sample_count"], 19)

    def test_history_windows_preserve_missing_trade_day_as_incomplete(self):
        rows = [
            {
                "trade_date": f"2026-07-{day:02d}",
                "metric": None if day == 10 else day,
            }
            for day in range(1, 21)
        ]

        result = build_history_windows(
            rows,
            target_date="2026-07-20",
            value_key="metric",
            requested_windows=(20,),
        )["20"]

        self.assertEqual(result["observed_trade_day_count"], 20)
        self.assertEqual(result["sample_count"], 19)
        self.assertEqual(result["coverage_status"], "insufficient")
        self.assertIn(
            {"trade_date": "2026-07-10", "value": None},
            result["values"],
        )

    def test_real_calendar_leaves_holes_instead_of_substituting_older_dates(self):
        calendar = [f'2026-07-{day:02d}' for day in range(2, 22)]
        rows = [{'trade_date': f'2026-07-{day:02d}', 'metric': day}
                for day in range(1, 22) if day != 10]
        result = build_history_windows(rows, target_date=calendar[-1], value_key='metric',
                                       requested_windows=(20,), trade_dates=calendar)['20']
        self.assertEqual(result['observed_trade_day_count'], 20)
        self.assertEqual(result['sample_count'], 19)
        self.assertEqual(result['values'][0]['trade_date'], calendar[0])
        self.assertIn({'trade_date': '2026-07-10', 'value': None}, result['values'])
        self.assertEqual(result['coverage_status'], 'insufficient')


def _member_rows(product, *, long_qty, short_qty, long_change, short_change):
    contract = f"{product}2608"
    common = {
        "trade_date": "2026-08-19",
        "source_date": "2026-08-19",
        "query_date": "2026-08-19",
        "product_code": product,
        "contract_code": contract,
        "member_name": "中信期货(代客)",
        "rank_no": 1,
    }
    return [
        {**common, "rank_type": "long", "quantity": long_qty, "daily_change": long_change},
        {**common, "rank_type": "short", "quantity": short_qty, "daily_change": short_change},
    ]


def _contract_row(
    product,
    *,
    contract=None,
    settlement=100,
    open_interest=1000,
    previous_open_interest=990,
):
    return {
        "trade_date": "2026-08-19",
        "source_date": "2026-08-19",
        "query_date": "2026-08-19",
        "product_code": product,
        "contract_code": contract or f"{product}2608",
        "settlement_price": settlement,
        "previous_settlement_price": settlement - 1,
        "open_interest": open_interest,
        "previous_open_interest": previous_open_interest,
        "contract_multiplier": CFFEX_CONTRACT_MULTIPLIERS[product],
    }


def _top20_rows(product, values, *, current):
    contract = f"{product}2608"
    if current:
        long_quantity = values["current_long"]
        short_quantity = values["current_short"]
        long_change = values["long_daily_change"]
        short_change = values["short_daily_change"]
        trade_date = "2026-08-19"
    else:
        long_quantity = 100000
        short_quantity = long_quantity + values["previous_net_short"]
        long_change = 0
        short_change = 0
        trade_date = "2026-08-18"
    common = {
        "trade_date": trade_date,
        "source_date": trade_date,
        "query_date": "2026-08-19",
        "product_code": product,
        "contract_code": contract,
        "rank_no": 1,
    }
    return [
        {**common, "rank_type": "long", "member_name": "多头会员", "quantity": long_quantity, "daily_change": long_change},
        {**common, "rank_type": "short", "member_name": "空头会员", "quantity": short_quantity, "daily_change": short_change},
    ]


if __name__ == "__main__":
    unittest.main()
