import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from observability.opik_runtime import build_report_run_observer, opik_enabled


class StubSpan:
    def __init__(self):
        self.ended = False

    def end(self):
        self.ended = True


class StubTrace:
    def __init__(self, payload):
        self.payload = payload
        self.spans = []
        self.end_payload = None

    def span(self, **kwargs):
        span = StubSpan()
        self.spans.append({"payload": kwargs, "span": span})
        return span

    def end(self, **kwargs):
        self.end_payload = kwargs


class StubClient:
    def __init__(self):
        self.traces = []
        self.flushed = False

    def trace(self, **kwargs):
        trace = StubTrace(kwargs)
        self.traces.append(trace)
        return trace

    def flush(self):
        self.flushed = True


class OpikObservabilityRuntimeTest(unittest.TestCase):
    def test_opik_observer_is_disabled_by_default_without_importing_opik(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(opik_enabled())
            observer = build_report_run_observer(run_name="daily-report.test")

        self.assertFalse(observer.enabled)

    def test_opik_observer_records_step_and_finishes_with_injected_client(self):
        client = StubClient()
        with patch.dict(os.environ, {"A_DAILY_REPORT_OPIK_ENABLED": "1"}, clear=True):
            observer = build_report_run_observer(
                run_name="daily-report.test",
                trace_input={"target_date": "2026-05-24"},
                metadata={"runner": "unit"},
                client_factory=lambda: client,
            )

        self.assertTrue(observer.enabled)
        observer.record_step(
            "load_data",
            status="success",
            input_payload={"target_date": "2026-05-24"},
            output_payload={"data_keys": ["market"]},
        )
        observer.finish(status="success", output_payload={"finding_count": 0})

        trace = client.traces[0]
        self.assertEqual(trace.payload["name"], "daily-report.test")
        self.assertEqual(trace.spans[0]["payload"]["name"], "load_data")
        self.assertEqual(trace.spans[0]["payload"]["output"]["status"], "success")
        self.assertTrue(trace.spans[0]["span"].ended)
        self.assertEqual(trace.end_payload["output"]["status"], "success")
        self.assertTrue(client.flushed)

    def test_opik_observer_degrades_to_noop_when_client_is_unavailable(self):
        with patch.dict(os.environ, {"A_DAILY_REPORT_OPIK_ENABLED": "1"}, clear=True):
            observer = build_report_run_observer(
                run_name="daily-report.test",
                client_factory=lambda: (_ for _ in ()).throw(RuntimeError("opik unavailable")),
            )

        self.assertFalse(observer.enabled)
        self.assertEqual(observer.reason, "client_unavailable")

    def test_opik_observer_degrades_to_noop_when_package_is_missing(self):
        with patch.dict(os.environ, {"A_DAILY_REPORT_OPIK_ENABLED": "1"}, clear=True), \
             patch("importlib.import_module", side_effect=ImportError("missing opik")):
            observer = build_report_run_observer(run_name="daily-report.test")

        self.assertFalse(observer.enabled)
        self.assertEqual(observer.reason, "client_unavailable")

    def test_opik_observer_degrades_to_noop_when_trace_is_unavailable(self):
        class EmptyClient:
            def trace(self, **kwargs):
                return None

        with patch.dict(os.environ, {"A_DAILY_REPORT_OPIK_ENABLED": "1"}, clear=True):
            observer = build_report_run_observer(
                run_name="daily-report.test",
                client_factory=lambda: EmptyClient(),
            )

        self.assertFalse(observer.enabled)
        self.assertEqual(observer.reason, "trace_unavailable")

    def test_opik_observer_swallows_client_write_errors(self):
        class BrokenTrace:
            def span(self, **kwargs):
                raise RuntimeError("span failed")

            def end(self, **kwargs):
                raise RuntimeError("trace end failed")

        class BrokenClient:
            def trace(self, **kwargs):
                return BrokenTrace()

            def flush(self):
                raise RuntimeError("flush failed")

        with patch.dict(os.environ, {"A_DAILY_REPORT_OPIK_ENABLED": "1"}, clear=True):
            observer = build_report_run_observer(
                run_name="daily-report.test",
                client_factory=lambda: BrokenClient(),
            )

        self.assertTrue(observer.enabled)
        observer.record_step("load_data", status="success")
        observer.finish(status="success")


if __name__ == "__main__":
    unittest.main()
