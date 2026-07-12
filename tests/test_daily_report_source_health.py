import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class DailyReportSourceHealthTest(unittest.TestCase):
    def setUp(self):
        import daily_report_source_health as health

        self._investor_qa_fetcher_patch = patch.object(
            health,
            "fetch_investor_qa_rows",
            side_effect=self._ok_investor_qa,
        )
        self._investor_qa_fetcher_patch.start()

    def tearDown(self):
        self._investor_qa_fetcher_patch.stop()

    def _env(self):
        return {
            "TUSHARE_TOKEN": "token-secret",
            "TUSHARE_HTTP_URL": "https://ai-tool.indevs.in/tushare/pro,https://tushare.indevs.in/tushare/pro",
            "XUEQIU_COOKIE": "xq_a_token=cookie-secret",
            "QUICKTINY_TOKEN": "quicktiny-secret",
            "DATABASE_URL": "postgresql://localhost/report",
            "INVESTOR_QA_ENDPOINT_URL": "https://qa.example/investor-qa",
        }

    def _env_without(self, *keys):
        env = self._env()
        for key in keys:
            env.pop(key, None)
        return env

    def _ok_tushare(self, **kwargs):
        return {
            "ok": True,
            "provider": "tushare.b.index_basic",
            "checks": [{"name": "index_basic", "row_count": 1}],
        }

    def _ok_hot(self, **kwargs):
        return {
            "provider": "xueqiu.hot_stock.type22",
            "status": "ok",
            "rows": [{"full_code": "SZ000001", "code": "000001"}],
        }

    def _ok_argument(self, symbols, **kwargs):
        return {
            "provider": "xueqiu.hot_stock.argument",
            "status": "ok",
            "rows": [{"full_code": symbols[0], "argument": "测试理由"}],
        }

    def _ok_investor_qa(self, *args, **kwargs):
        return [{"code": "000001", "question": "测试问题", "answer": "测试答复"}]

    def test_source_health_writes_json_and_bear_html_contract(self):
        import daily_report_source_health as health

        hot_calls = []

        def hot_once(**kwargs):
            hot_calls.append(kwargs)
            return self._ok_hot(**kwargs)

        with tempfile.TemporaryDirectory() as tmpdir:
            payload = health.run_source_health_check(
                "2026-07-08",
                root_dir=tmpdir,
                env=self._env(),
                tushare_checker=self._ok_tushare,
                xueqiu_hot_fetcher=hot_once,
                xueqiu_argument_fetcher=self._ok_argument,
                quicktiny_fetcher=lambda **kwargs: {"data": [{"code": "000001"}]},
                postgres_checker=lambda: True,
            )

            self.assertEqual(payload["schema_version"], "daily_report_source_health.v1")
            self.assertEqual(payload["overall_result"], "ready")
            self.assertIn("stop_reasons", payload)
            self.assertIn("blocking_failures", payload)
            self.assertTrue(payload["checks"])

            json_path = Path(payload["artifacts"]["json_path"])
            html_path = Path(payload["artifacts"]["html_path"])
            self.assertTrue(json_path.exists())
            self.assertTrue(html_path.exists())
            saved = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["target_date"], "2026-07-08")
            self.assertEqual(saved["artifacts"]["html_path"], str(html_path))
            self.assertEqual(saved["artifacts"]["json_path"], str(json_path))
            html = html_path.read_text(encoding="utf-8")
            self.assertIn("日报生成前数据源检查", html)
            self.assertIn("bear-source-health", html)
            self.assertIn("overall-pill", html)
            self.assertIn("table-wrap", html)
            self.assertIn("status-mark", html)
            self.assertIn("✓", html)
            self.assertIn("×", html)
            self.assertIn("-", html)
            self.assertIn("数据源任务", html)
            self.assertEqual(len(hot_calls), 1)

    def test_terminal_summary_uses_readable_labels_when_optional_qa_is_empty(self):
        import daily_report_source_health as health

        payload = health.run_source_health_check(
            "2026-07-08",
            env=self._env_without("INVESTOR_QA_ENDPOINT_URL"),
            write_artifacts=False,
            tushare_checker=self._ok_tushare,
            xueqiu_hot_fetcher=self._ok_hot,
            xueqiu_argument_fetcher=self._ok_argument,
            quicktiny_fetcher=lambda **kwargs: {"data": [{"code": "000001"}]},
            investor_qa_fetcher=lambda *args, **kwargs: [],
            postgres_checker=lambda: True,
        )

        lines = health.render_source_health_terminal_lines(payload)
        text = "\n".join(lines)
        self.assertIn("生成前数据源检查: 可生成 / 2026-07-08", lines[0])
        self.assertNotIn("stop_generation", text)
        self.assertEqual([], payload["stop_reasons"])
        self.assertTrue(any("投资者问答" in item for item in payload["warnings"]))
        self.assertIn("QuickTiny 异动检测: 可生成", text)

    def test_live_source_checks_run_independent_sources_in_parallel_and_keep_order(self):
        import daily_report_source_health as health

        def slow_tushare(**kwargs):
            time.sleep(0.12)
            return self._ok_tushare(**kwargs)

        def slow_postgres():
            time.sleep(0.12)
            return True

        def slow_hot(**kwargs):
            time.sleep(0.12)
            return self._ok_hot(**kwargs)

        def slow_argument(symbols, **kwargs):
            time.sleep(0.12)
            return self._ok_argument(symbols, **kwargs)

        def slow_quicktiny(**kwargs):
            time.sleep(0.12)
            return {"data": [{"code": "000001"}]}

        started = time.perf_counter()
        payload = health.run_source_health_check(
            "2026-07-08",
            env=self._env(),
            write_artifacts=False,
            tushare_checker=slow_tushare,
            xueqiu_hot_fetcher=slow_hot,
            xueqiu_argument_fetcher=slow_argument,
            quicktiny_fetcher=slow_quicktiny,
            postgres_checker=slow_postgres,
            source_timeout_seconds=1,
        )
        elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 0.45)
        self.assertEqual(
            [item["id"] for item in payload["checks"]],
            [
                "tushare.runtime",
                "postgres.fact_store",
                "xueqiu.hot_stock",
                "xueqiu.hot_argument",
                "quicktiny.exchange_monitor",
                "iwencai.api",
                "xuangubao.news",
                "investor.qa",
                "deepseek.calendar_llm",
            ],
        )
        self.assertEqual(payload["overall_result"], "ready")

    def test_tushare_health_uses_light_probe_timeout(self):
        import daily_report_source_health as health

        received_timeouts = []

        def recording_tushare(**kwargs):
            received_timeouts.append(kwargs.get("timeout_seconds"))
            return self._ok_tushare(**kwargs)

        payload = health.run_source_health_check(
            "2026-07-08",
            env=self._env(),
            write_artifacts=False,
            tushare_checker=recording_tushare,
            xueqiu_hot_fetcher=self._ok_hot,
            xueqiu_argument_fetcher=self._ok_argument,
            quicktiny_fetcher=lambda **kwargs: {"data": [{"code": "000001"}]},
            postgres_checker=lambda: True,
        )

        self.assertEqual(payload["overall_result"], "ready")
        self.assertEqual(received_timeouts, [health.TUSHARE_PROBE_TIMEOUT_SECONDS])
        self.assertLess(health.TUSHARE_SOURCE_TIMEOUT_SECONDS, 60)

    def test_tushare_health_retries_once_before_stopping_generation(self):
        import daily_report_source_health as health

        calls = []

        def flaky_tushare(**kwargs):
            calls.append(kwargs.get("timeout_seconds"))
            if len(calls) == 1:
                return {
                    "ok": False,
                    "provider": "tushare.b.index_basic",
                    "error_message": "B channel read timeout",
                }
            return self._ok_tushare(**kwargs)

        payload = health.run_source_health_check(
            "2026-07-08",
            env=self._env(),
            write_artifacts=False,
            tushare_checker=flaky_tushare,
            xueqiu_hot_fetcher=self._ok_hot,
            xueqiu_argument_fetcher=self._ok_argument,
            quicktiny_fetcher=lambda **kwargs: {"data": [{"code": "000001"}]},
            postgres_checker=lambda: True,
        )

        row = next(item for item in payload["checks"] if item["id"] == "tushare.runtime")
        self.assertEqual(calls, [health.TUSHARE_PROBE_TIMEOUT_SECONDS, health.TUSHARE_PROBE_TIMEOUT_SECONDS])
        self.assertEqual(row["result"], "pass")
        self.assertEqual(payload["overall_result"], "ready")

    def test_xueqiu_argument_reuses_hot_rows_without_refetch(self):
        import daily_report_source_health as health

        hot_calls = []
        argument_symbols = []

        def hot_fetcher(**kwargs):
            hot_calls.append(kwargs)
            return {
                "provider": "xueqiu.hot_stock.type22",
                "status": "ok",
                "rows": [
                    {"full_code": "SH600000", "code": "600000"},
                    {"symbol": "SZ000001", "code": "000001"},
                ],
            }

        def argument_fetcher(symbols, **kwargs):
            argument_symbols.append(list(symbols))
            return {
                "provider": "xueqiu.hot_stock.argument",
                "status": "ok",
                "rows": [{"full_code": symbol, "argument": "测试理由"} for symbol in symbols],
            }

        payload = health.run_source_health_check(
            "2026-07-08",
            env=self._env(),
            write_artifacts=False,
            tushare_checker=self._ok_tushare,
            xueqiu_hot_fetcher=hot_fetcher,
            xueqiu_argument_fetcher=argument_fetcher,
            quicktiny_fetcher=lambda **kwargs: {"data": [{"code": "000001"}]},
            postgres_checker=lambda: True,
        )

        argument = next(item for item in payload["checks"] if item["id"] == "xueqiu.hot_argument")
        self.assertEqual(len(hot_calls), 1)
        self.assertEqual(argument_symbols, [["SH600000", "SZ000001"]])
        self.assertEqual(argument["row_count"], 2)

    def test_tushare_missing_credentials_stops_generation(self):
        import daily_report_source_health as health

        payload = health.run_source_health_check(
            "2026-07-08",
            env=self._env_without("TUSHARE_TOKEN", "TUSHARE_HTTP_URL"),
            write_artifacts=False,
            tushare_checker=self._ok_tushare,
            xueqiu_hot_fetcher=self._ok_hot,
            xueqiu_argument_fetcher=self._ok_argument,
            quicktiny_fetcher=lambda **kwargs: {"data": [{"code": "000001"}]},
            postgres_checker=lambda: True,
        )

        self.assertEqual(payload["overall_result"], "stop_generation")
        self.assertTrue(any("Tushare" in item for item in payload["stop_reasons"]))

    def test_tushare_a_proxy_is_probed_and_can_pass(self):
        import daily_report_source_health as health

        env = self._env()
        env["TUSHARE_HTTP_URL"] = "https://fastapic.stockai888.top"
        calls = []

        def ok_a_channel(**kwargs):
            calls.append(kwargs)
            return {
                "ok": True,
                "provider": "tushare.pro.index_basic",
                "checks": [{"name": "index_basic", "row_count": 1}],
            }

        payload = health.run_source_health_check(
            "2026-07-08",
            env=env,
            write_artifacts=False,
            tushare_checker=ok_a_channel,
            xueqiu_hot_fetcher=self._ok_hot,
            xueqiu_argument_fetcher=self._ok_argument,
            quicktiny_fetcher=lambda **kwargs: {"data": [{"code": "000001"}]},
            postgres_checker=lambda: True,
        )

        row = next(item for item in payload["checks"] if item["id"] == "tushare.runtime")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["token"], env["TUSHARE_TOKEN"])
        self.assertEqual(calls[0]["http_url"], env["TUSHARE_HTTP_URL"])
        self.assertEqual(row["task"], "Tushare A 通道")
        self.assertEqual(row["provider"], "tushare.pro.index_basic")
        self.assertEqual(row["result"], "pass")
        self.assertEqual(payload["overall_result"], "ready")

    def test_xueqiu_missing_cookie_stops_generation(self):
        import daily_report_source_health as health

        payload = health.run_source_health_check(
            "2026-07-08",
            env=self._env_without("XUEQIU_COOKIE"),
            write_artifacts=False,
            tushare_checker=self._ok_tushare,
            xueqiu_hot_fetcher=self._ok_hot,
            xueqiu_argument_fetcher=self._ok_argument,
            quicktiny_fetcher=lambda **kwargs: {"data": [{"code": "000001"}]},
            postgres_checker=lambda: True,
        )

        self.assertEqual(payload["overall_result"], "stop_generation")
        self.assertTrue(any("雪球" in item for item in payload["stop_reasons"]))

    def test_xueqiu_login_failure_marks_suspected_expired(self):
        import daily_report_source_health as health

        def failed_hot(**kwargs):
            return {
                "provider": "xueqiu.hot_stock.type22",
                "status": "error",
                "rows": [],
                "diagnostic_note": "雪球登录态失效或缺失，关键数据不完整，停止生成",
            }

        payload = health.run_source_health_check(
            "2026-07-08",
            env=self._env(),
            write_artifacts=False,
            tushare_checker=self._ok_tushare,
            xueqiu_hot_fetcher=failed_hot,
            xueqiu_argument_fetcher=self._ok_argument,
            quicktiny_fetcher=lambda **kwargs: {"data": [{"code": "000001"}]},
            postgres_checker=lambda: True,
        )
        hot = next(item for item in payload["checks"] if item["id"] == "xueqiu.hot_stock")
        self.assertEqual(hot["credential_status"], "suspected_expired")
        self.assertEqual(payload["overall_result"], "stop_generation")

    def test_required_source_credentials_stop_generation(self):
        import daily_report_source_health as health

        payload = health.run_source_health_check(
            "2026-07-08",
            env={
                "TUSHARE_TOKEN": "token-secret",
                "TUSHARE_HTTP_URL": "https://ai-tool.indevs.in/tushare/pro",
                "XUEQIU_COOKIE": "xq_a_token=cookie-secret",
            },
            write_artifacts=False,
            tushare_checker=self._ok_tushare,
            xueqiu_hot_fetcher=self._ok_hot,
            xueqiu_argument_fetcher=self._ok_argument,
            investor_qa_fetcher=lambda *args, **kwargs: [],
            postgres_checker=lambda: True,
        )

        self.assertEqual(payload["overall_result"], "stop_generation")
        self.assertTrue(any("QuickTiny" in item for item in payload["stop_reasons"]))
        self.assertFalse(any("投资者问答" in item for item in payload["stop_reasons"]))
        self.assertTrue(any("投资者问答" in item for item in payload["warnings"]))

    def test_quicktiny_empty_payload_stops_generation(self):
        import daily_report_source_health as health

        payload = health.run_source_health_check(
            "2026-07-08",
            env=self._env(),
            write_artifacts=False,
            tushare_checker=self._ok_tushare,
            xueqiu_hot_fetcher=self._ok_hot,
            xueqiu_argument_fetcher=self._ok_argument,
            quicktiny_fetcher=lambda **kwargs: {"data": []},
            postgres_checker=lambda: True,
        )

        row = next(item for item in payload["checks"] if item["id"] == "quicktiny.exchange_monitor")
        self.assertEqual(row["result"], "fail")
        self.assertEqual(row["row_count"], 0)
        self.assertEqual(row["required_for_generation"], True)
        self.assertEqual(payload["overall_result"], "stop_generation")
        self.assertTrue(any("QuickTiny" in item for item in payload["stop_reasons"]))

    def test_investor_qa_missing_endpoint_warns_without_stopping_generation(self):
        import daily_report_source_health as health

        payload = health.run_source_health_check(
            "2026-07-08",
            env=self._env_without("INVESTOR_QA_ENDPOINT_URL"),
            write_artifacts=False,
            tushare_checker=self._ok_tushare,
            xueqiu_hot_fetcher=self._ok_hot,
            xueqiu_argument_fetcher=self._ok_argument,
            quicktiny_fetcher=lambda **kwargs: {"data": [{"code": "000001"}]},
            investor_qa_fetcher=lambda *args, **kwargs: [],
            postgres_checker=lambda: True,
        )

        row = next(item for item in payload["checks"] if item["id"] == "investor.qa")
        self.assertEqual(row["result"], "warning")
        self.assertEqual(row["credential_status"], "ok")
        self.assertEqual(row["target_date_status"], "not_applicable")
        self.assertIn("风险快照缺少这类澄清来源", row["advice"])
        self.assertEqual(row["required_for_generation"], False)
        self.assertEqual(payload["overall_result"], "ready")

    def test_investor_qa_tushare_rows_pass_without_external_endpoint(self):
        import daily_report_source_health as health

        payload = health.run_source_health_check(
            "2026-07-08",
            env=self._env_without("INVESTOR_QA_ENDPOINT_URL"),
            write_artifacts=False,
            tushare_checker=self._ok_tushare,
            xueqiu_hot_fetcher=self._ok_hot,
            xueqiu_argument_fetcher=self._ok_argument,
            quicktiny_fetcher=lambda **kwargs: {"data": [{"code": "000001"}]},
            investor_qa_fetcher=lambda *args, **kwargs: [{"code": "000001", "question": "测试问题"}],
            postgres_checker=lambda: True,
        )

        row = next(item for item in payload["checks"] if item["id"] == "investor.qa")
        self.assertEqual(payload["overall_result"], "ready")
        self.assertEqual(row["result"], "pass")
        self.assertEqual(row["provider"], "tushare.irm_qa")
        self.assertEqual(row["row_count"], 1)

    def test_investor_qa_empty_payload_stops_generation(self):
        import daily_report_source_health as health

        payload = health.run_source_health_check(
            "2026-07-08",
            env=self._env(),
            write_artifacts=False,
            tushare_checker=self._ok_tushare,
            xueqiu_hot_fetcher=self._ok_hot,
            xueqiu_argument_fetcher=self._ok_argument,
            quicktiny_fetcher=lambda **kwargs: {"data": [{"code": "000001"}]},
            investor_qa_fetcher=lambda *args, **kwargs: [],
            postgres_checker=lambda: True,
        )

        row = next(item for item in payload["checks"] if item["id"] == "investor.qa")
        self.assertEqual(row["result"], "fail")
        self.assertEqual(row["connectivity_status"], "ok")
        self.assertEqual(row["target_date_status"], "missing")
        self.assertEqual(row["row_count"], 0)
        self.assertEqual(payload["overall_result"], "stop_generation")

    def test_investor_qa_probe_uses_runtime_order_and_recent_window(self):
        import daily_report_source_health as health

        calls = []

        def investor_qa_fetcher(*args, **kwargs):
            calls.append((args, kwargs))
            if kwargs.get("use_tushare"):
                return []
            return [{"code": "000001", "question": "测试问题"}]

        payload = health.run_source_health_check(
            "2026-07-08",
            env=self._env(),
            write_artifacts=False,
            tushare_checker=self._ok_tushare,
            xueqiu_hot_fetcher=self._ok_hot,
            xueqiu_argument_fetcher=self._ok_argument,
            quicktiny_fetcher=lambda **kwargs: {"data": [{"code": "000001"}]},
            investor_qa_fetcher=investor_qa_fetcher,
            postgres_checker=lambda: True,
        )

        row = next(item for item in payload["checks"] if item["id"] == "investor.qa")
        self.assertEqual(payload["overall_result"], "ready")
        self.assertEqual(row["result"], "pass")
        self.assertEqual(row["provider"], "investor_qa.endpoint")
        self.assertEqual(row["row_count"], 1)
        self.assertEqual(calls[0][0], ("2026-07-08",))
        self.assertEqual(calls[0][1]["endpoint_url"], "")
        self.assertEqual(calls[0][1]["use_tushare"], True)
        self.assertEqual(calls[0][1]["lookback_trade_days"], 10)
        self.assertEqual(calls[1][0], ("2026-07-08",))
        self.assertEqual(calls[1][1]["endpoint_url"], "https://qa.example/investor-qa")
        self.assertEqual(calls[1][1]["use_tushare"], False)
        self.assertEqual(calls[1][1]["lookback_trade_days"], 10)

    def test_investor_qa_external_success_after_official_timeout_reports_total_duration(self):
        import daily_report_source_health as health

        with patch.object(
            health,
            "_run_with_timeout",
            side_effect=[
                {"status": "timeout", "value": None, "duration_ms": 5000, "error": "source health check timed out after 5s"},
                {"status": "ok", "value": [{"code": "000001", "question": "测试问题"}], "duration_ms": 300},
            ],
        ):
            row = health._investor_qa_check(
                self._env(),
                target_date="2026-07-08",
                fetcher=lambda *args, **kwargs: [],
                timeout_seconds=15,
            )

        self.assertEqual(row["result"], "pass")
        self.assertEqual(row["provider"], "investor_qa.endpoint")
        self.assertEqual(row["connectivity_status"], "ok")
        self.assertEqual(row["target_date_status"], "covered")
        self.assertEqual(row["duration_ms"], 5300)

    def test_postgres_missing_env_uses_available_local_fact_store(self):
        import daily_report_source_health as health

        payload = health.run_source_health_check(
            "2026-07-08",
            env=self._env_without("DATABASE_URL", "A_DAILY_REPORT_DATABASE_URL"),
            write_artifacts=False,
            tushare_checker=self._ok_tushare,
            xueqiu_hot_fetcher=self._ok_hot,
            xueqiu_argument_fetcher=self._ok_argument,
            quicktiny_fetcher=lambda **kwargs: {"data": [{"code": "000001"}]},
            postgres_checker=lambda: {"connected": True, "covered": False, "row_count": 0},
        )

        row = next(item for item in payload["checks"] if item["id"] == "postgres.fact_store")
        self.assertEqual(row["result"], "pass")
        self.assertEqual(row["credential_status"], "ok")
        self.assertEqual(row["connectivity_status"], "ok")
        self.assertEqual(row["target_date_status"], "not_checked")
        self.assertEqual(payload["overall_result"], "ready")

    def test_postgres_missing_env_and_unavailable_store_stops_generation(self):
        import daily_report_source_health as health

        payload = health.run_source_health_check(
            "2026-07-08",
            env=self._env_without("DATABASE_URL", "A_DAILY_REPORT_DATABASE_URL"),
            write_artifacts=False,
            tushare_checker=self._ok_tushare,
            xueqiu_hot_fetcher=self._ok_hot,
            xueqiu_argument_fetcher=self._ok_argument,
            quicktiny_fetcher=lambda **kwargs: {"data": [{"code": "000001"}]},
            postgres_checker=lambda: {"connected": False, "covered": False, "row_count": 0},
        )

        row = next(item for item in payload["checks"] if item["id"] == "postgres.fact_store")
        self.assertEqual(row["result"], "fail")
        self.assertEqual(row["credential_status"], "missing")
        self.assertEqual(row["connectivity_status"], "failed")
        self.assertEqual(payload["overall_result"], "stop_generation")

    def test_single_source_timeout_is_reported_without_hanging(self):
        import daily_report_source_health as health

        def slow_hot(**kwargs):
            time.sleep(0.2)
            return {"provider": "xueqiu.hot_stock.type22", "status": "ok", "rows": []}

        started = time.perf_counter()
        payload = health.run_source_health_check(
            "2026-07-08",
            env=self._env(),
            write_artifacts=False,
            source_timeout_seconds=0.01,
            tushare_checker=self._ok_tushare,
            xueqiu_hot_fetcher=slow_hot,
            xueqiu_argument_fetcher=self._ok_argument,
            quicktiny_fetcher=lambda **kwargs: {"data": [{"code": "000001"}]},
            postgres_checker=lambda: True,
        )

        self.assertLess(time.perf_counter() - started, 0.2)
        hot = next(item for item in payload["checks"] if item["id"] == "xueqiu.hot_stock")
        self.assertEqual(hot["connectivity_status"], "timeout")
        self.assertEqual(payload["overall_result"], "stop_generation")

    def test_timeout_thread_does_not_hold_process_open(self):
        code = (
            "import sys, time; "
            f"sys.path.insert(0, {str(ROOT / 'scripts')!r}); "
            "import daily_report_source_health as health; "
            "started=time.perf_counter(); "
            "print(health._run_with_timeout(lambda: time.sleep(2), timeout_seconds=0.05)['status']); "
            "print(round(time.perf_counter()-started, 2))"
        )
        started = time.perf_counter()
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=3.0,
            check=False,
        )

        elapsed = time.perf_counter() - started
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertLess(elapsed, 2.0)
        self.assertIn("timeout", result.stdout)
        internal_elapsed = float(result.stdout.splitlines()[-1])
        self.assertLess(internal_elapsed, 0.5)

    def test_postgres_only_checks_target_date_without_live_sources(self):
        import daily_report_source_health as health

        payload = health.run_source_health_check(
            "2026-07-08",
            env={"DATABASE_URL": "postgresql://user:pass@localhost/report"},
            postgres_only=True,
            write_artifacts=False,
            postgres_checker=lambda: {"connected": True, "covered": True, "row_count": 9},
            tushare_checker=lambda **kwargs: (_ for _ in ()).throw(AssertionError("Tushare called")),
            xueqiu_hot_fetcher=lambda **kwargs: (_ for _ in ()).throw(AssertionError("Xueqiu called")),
        )

        self.assertEqual(payload["overall_result"], "ready")
        self.assertEqual([item["id"] for item in payload["checks"]], ["postgres.fact_store"])
        self.assertEqual(payload["checks"][0]["target_date_status"], "covered")
        self.assertEqual(payload["checks"][0]["row_count"], 9)

    def test_postgres_only_uses_configured_source_timeout_for_local_fact_probe(self):
        import daily_report_source_health as health

        received_timeouts = []

        def capture_timeout(checker, *, timeout_seconds):
            received_timeouts.append(timeout_seconds)
            return {
                "status": health.STATUS_OK,
                "value": {"connected": True, "covered": True, "row_count": 9},
                "duration_ms": 1,
            }

        with patch.object(health, "_run_with_timeout", side_effect=capture_timeout):
            payload = health.run_source_health_check(
                "2026-07-10",
                env={},
                postgres_only=True,
                write_artifacts=False,
                source_timeout_seconds=10,
            )

        self.assertEqual(received_timeouts, [10])
        self.assertEqual(payload["overall_result"], "ready")

    def test_postgres_only_missing_target_date_stops_generation(self):
        import daily_report_source_health as health

        payload = health.run_source_health_check(
            "2026-07-08",
            env={},
            postgres_only=True,
            write_artifacts=False,
            postgres_checker=lambda: {"connected": True, "covered": False, "row_count": 0},
        )

        self.assertEqual(payload["overall_result"], "stop_generation")
        row = payload["checks"][0]
        self.assertEqual(row["id"], "postgres.fact_store")
        self.assertEqual(row["target_date_status"], "missing")
        self.assertEqual(row["result"], "fail")

    def test_postgres_only_default_probe_rejects_empty_metadata_snapshot(self):
        import daily_report_source_health as health

        class FakeService:
            repository = object()

            def daily_report_fact_coverage(self, target_date):
                return {
                    "tables": {
                        "daily_report_fact_fields": {"target_count": 0},
                        "market_cycle_days": {"target_count": 0},
                    }
                }

            def load_daily_report_snapshot(self, target_date):
                return {
                    "source": f"postgresql://daily-report-facts/{target_date}",
                    "field_count": 0,
                    "target_field_count": 0,
                    "structured_counts": {},
                    "structured_fact_count": 0,
                    "target_structured_fact_count": 0,
                    "data": {},
                }

        with patch.object(health.DatabaseService, "from_environment", return_value=FakeService()):
            payload = health.run_source_health_check(
                "2026-07-08",
                env={"DATABASE_URL": "postgresql://user:pass@localhost/report"},
                postgres_only=True,
                write_artifacts=False,
            )

        self.assertEqual(payload["overall_result"], "stop_generation")
        self.assertEqual(payload["checks"][0]["target_date_status"], "missing")
        self.assertEqual(payload["checks"][0]["row_count"], 0)

    def test_postgres_only_default_probe_accepts_target_structured_count(self):
        import daily_report_source_health as health

        class FakeService:
            repository = object()

            def daily_report_fact_coverage(self, target_date):
                return {"tables": {"market_cycle_days": {"target_count": 1}}}

            def load_daily_report_snapshot(self, target_date):
                return {
                    "source": f"postgresql://daily-report-facts/{target_date}",
                    "field_count": 0,
                    "target_field_count": 0,
                    "structured_counts": {"target_cycle_calendar_rows": 1},
                    "structured_fact_count": 1,
                    "target_structured_fact_count": 1,
                    "data": {},
                }

        with patch.object(health.DatabaseService, "from_environment", return_value=FakeService()):
            payload = health.run_source_health_check(
                "2026-07-08",
                env={"DATABASE_URL": "postgresql://user:pass@localhost/report"},
                postgres_only=True,
                write_artifacts=False,
            )

        self.assertEqual(payload["overall_result"], "ready")
        self.assertEqual(payload["checks"][0]["target_date_status"], "covered")
        self.assertEqual(payload["checks"][0]["row_count"], 1)

    def test_redaction_removes_secrets_from_text(self):
        import daily_report_source_health as health

        text = (
            "Bearer abc.secret token=quicktiny-secret "
            "postgresql://user:pass@localhost/db XUEQIU_COOKIE=xq_a_token=cookie-secret "
            "IWENCAI_API_KEY=api-secret"
        )
        redacted = health.redact_sensitive_text(
            text,
            env={
                "XUEQIU_COOKIE": "xq_a_token=cookie-secret",
                "DATABASE_URL": "postgresql://user:pass@localhost/db",
                "IWENCAI_API_KEY": "api-secret",
            },
        )

        self.assertNotIn("abc.secret", redacted)
        self.assertNotIn("quicktiny-secret", redacted)
        self.assertNotIn("user:pass", redacted)
        self.assertNotIn("cookie-secret", redacted)
        self.assertNotIn("api-secret", redacted)

    def test_artifacts_redact_provider_and_error_text(self):
        import daily_report_source_health as health

        def provider_with_secret(**kwargs):
            return {
                "ok": True,
                "provider": "https://provider.example/check?token=token-secret",
                "checks": [{"name": "index_basic", "row_count": 1}],
            }

        def hot_with_secret(**kwargs):
            return {
                "provider": "https://xueqiu.example/hot?token=token-secret",
                "status": "ok",
                "rows": [{"full_code": "SZ000001", "code": "000001"}],
            }

        def argument_with_secret(symbols, **kwargs):
            return {
                "provider": "https://xueqiu.example/argument?cookie=xq_a_token=cookie-secret",
                "status": "ok",
                "rows": [{"full_code": symbols[0], "argument": "测试理由"}],
            }

        env = {
            **self._env(),
            "DATABASE_URL": "postgresql://user:pass@localhost/report",
            "IWENCAI_API_KEY": "api-secret",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = health.run_source_health_check(
                "2026-07-08",
                root_dir=tmpdir,
                env=env,
                tushare_checker=provider_with_secret,
                xueqiu_hot_fetcher=hot_with_secret,
                xueqiu_argument_fetcher=argument_with_secret,
                quicktiny_fetcher=lambda **kwargs: (_ for _ in ()).throw(
                    RuntimeError("Bearer abc.secret token=quicktiny-secret postgresql://user:pass@localhost/report")
                ),
                postgres_checker=lambda: True,
            )
            combined = (
                json.dumps(payload, ensure_ascii=False)
                + Path(payload["artifacts"]["json_path"]).read_text(encoding="utf-8")
                + Path(payload["artifacts"]["html_path"]).read_text(encoding="utf-8")
            )

        self.assertNotIn("token-secret", combined)
        self.assertNotIn("cookie-secret", combined)
        self.assertNotIn("quicktiny-secret", combined)
        self.assertNotIn("user:pass", combined)
        self.assertNotIn("api-secret", combined)
        self.assertNotIn("abc.secret", combined)

    def test_replay_mode_checks_snapshot_without_live_sources(self):
        import daily_report_source_health as health

        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_dir = Path(tmpdir) / "snapshots"
            snapshot_dir.mkdir(parents=True)
            (snapshot_dir / "2026-07-08.json").write_text("{}", encoding="utf-8")
            with patch.object(health, "_get_snapshot_path", return_value=str(snapshot_dir / "2026-07-08.json")):
                payload = health.run_source_health_check(
                    "2026-07-08",
                    root_dir=tmpdir,
                    replay=True,
                    env={},
                    write_artifacts=False,
                    tushare_checker=lambda **kwargs: (_ for _ in ()).throw(AssertionError("live source called")),
                )

        self.assertEqual(payload["overall_result"], "ready")
        self.assertEqual(payload["checks"][0]["id"], "replay.snapshot")


if __name__ == "__main__":
    unittest.main()
