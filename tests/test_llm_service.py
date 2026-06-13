import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class LlmServiceEnvTest(unittest.TestCase):
    def _load_llm_service_module(self, module_name="llm_service_under_test"):
        module_path = ROOT / "scripts" / "llm_service.py"
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_default_deepseek_model_uses_flash_when_env_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_path = Path(tmp_dir) / ".env"
            env_path.write_text("IWENCAI_API_KEY=from-file\n", encoding="utf-8")

            original_model = os.environ.pop("DEEPSEEK_MODEL", None)
            try:
                with patch("pathlib.Path.cwd", return_value=Path(tmp_dir)):
                    self._load_llm_service_module("llm_service_default_model_test")

                self.assertEqual(os.environ["DEEPSEEK_MODEL"], "deepseek-v4-flash")
            finally:
                if original_model is not None:
                    os.environ["DEEPSEEK_MODEL"] = original_model
                else:
                    os.environ.pop("DEEPSEEK_MODEL", None)

    def test_local_env_file_does_not_override_existing_environment(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_path = Path(tmp_dir) / ".env"
            env_path.write_text(
                "IWENCAI_API_KEY=from-file\nDEEPSEEK_MODEL=from-file-model\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"IWENCAI_API_KEY": "from-shell"}, clear=False):
                original_model = os.environ.pop("DEEPSEEK_MODEL", None)
                try:
                    with patch("pathlib.Path.cwd", return_value=Path(tmp_dir)):
                        self._load_llm_service_module("llm_service_env_test")

                    self.assertEqual(os.environ["IWENCAI_API_KEY"], "from-shell")
                    self.assertEqual(os.environ["DEEPSEEK_MODEL"], "from-file-model")
                finally:
                    if original_model is not None:
                        os.environ["DEEPSEEK_MODEL"] = original_model
                    else:
                        os.environ.pop("DEEPSEEK_MODEL", None)

    def test_llm_service_does_not_delegate_to_legacy_runtime_shim(self):
        calls = []

        def forbidden_export_or_default(*args, **kwargs):
            calls.append((args, kwargs))
            raise AssertionError("llm_service must not import from legacy_runtime_shim")

        fake_shim = types.SimpleNamespace(export_or_default=forbidden_export_or_default)
        with patch.dict(sys.modules, {"legacy_runtime_shim": fake_shim}):
            module = self._load_llm_service_module("llm_service_no_legacy_shim_test")

        self.assertEqual([], calls)
        self.assertTrue(callable(module.get_llm_service))

    def test_deepseek_provider_raises_on_reasoning_only_length_response(self):
        module = self._load_llm_service_module("llm_service_deepseek_length_test")

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "choices": [
                        {
                            "message": {
                                "content": "",
                                "reasoning_content": "还在推理，尚未输出最终答案",
                            },
                            "finish_reason": "length",
                        }
                    ]
                }

        with patch("requests.post", return_value=FakeResponse()):
            provider = module.DeepSeekHTTPProvider(api_key="key", base_url="https://api.deepseek.com")
            with self.assertRaisesRegex(RuntimeError, "reasoning-only length response"):
                provider.chat(
                    messages=[{"role": "user", "content": "只返回 OK"}],
                    model="deepseek-v4-flash",
                    temperature=0,
                    max_tokens=8,
                    timeout=3,
                )

    def test_llm_service_raises_deepseek_min_tokens_to_avoid_reasoning_only_response(self):
        module = self._load_llm_service_module("llm_service_deepseek_min_tokens_test")

        class CapturingProvider(module.BaseLLMProvider):
            def __init__(self):
                self.calls = []

            def chat(self, messages, model, temperature, max_tokens, timeout):
                self.calls.append(max_tokens)
                return "OK"

        module.reset_llm_service()
        service = module.LLMService(timeout=3)
        provider = CapturingProvider()
        service.provider = provider

        result = service.chat("只返回 OK", max_tokens=8, max_retries=0)

        self.assertEqual(result, "OK")
        self.assertEqual(provider.calls, [64])

    def test_llm_service_retries_reasoning_only_length_response_with_higher_tokens(self):
        module = self._load_llm_service_module("llm_service_reasoning_retry_test")

        class ReasoningRetryProvider(module.BaseLLMProvider):
            def __init__(self):
                self.calls = []

            def chat(self, messages, model, temperature, max_tokens, timeout):
                self.calls.append(max_tokens)
                if len(self.calls) == 1:
                    raise RuntimeError(
                        "deepseek reasoning-only length response; increase max_tokens "
                        "(reasoning_len=1750)"
                    )
                return "OK"

        module.reset_llm_service()
        service = module.LLMService(timeout=3)
        provider = ReasoningRetryProvider()
        service.provider = provider

        result = service.chat("只返回 OK", max_tokens=500, max_retries=1)

        self.assertEqual(result, "OK")
        self.assertEqual(provider.calls[0], 500)
        self.assertGreaterEqual(provider.calls[1], 2774)

    def test_adjudicate_calendar_event_news_evidence_parses_structured_result(self):
        module = self._load_llm_service_module("llm_service_calendar_news_adjudication_test")

        class CapturingProvider(module.BaseLLMProvider):
            def __init__(self):
                self.calls = []

            def chat(self, messages, model, temperature, max_tokens, timeout):
                self.calls.append(
                    {
                        "messages": messages,
                        "model": model,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "timeout": timeout,
                    }
                )
                return json.dumps(
                    {
                        "matched": True,
                        "evidence_index": 0,
                        "confidence": "高",
                        "match_reason": "同一场活动新闻，且含官方文件动作",
                        "classification_hint": "政策催化",
                        "related_sectors": ["政策催化"],
                        "policy_evidence": True,
                    },
                    ensure_ascii=False,
                )

        module.reset_llm_service()
        service = module.LLMService(timeout=3)
        provider = CapturingProvider()
        service.provider = provider

        result = service.adjudicate_calendar_event_news_evidence(
            {"title": "量子安全技术大会将于6月5日举办", "date": "2026-06-05"},
            [
                {
                    "title": "量子安全技术大会召开，工信部发布行业高质量发展实施方案",
                    "evidence_text": "工信部在大会期间发布行业高质量发展实施方案。",
                    "source_date": "2026-06-05",
                }
            ],
            report_date="2026-06-05",
        )

        self.assertTrue(result["matched"])
        self.assertEqual(result["evidence_index"], 0)
        self.assertEqual(result["confidence"], "高")
        self.assertTrue(result["policy_evidence"])
        prompt_text = provider.calls[0]["messages"][-1]["content"]
        self.assertIn("量子安全技术大会", prompt_text)
        self.assertIn("工信部", prompt_text)
        self.assertGreaterEqual(provider.calls[0]["max_tokens"], 64)

    def test_adjudicate_calendar_event_news_evidence_rejects_boolean_index_and_confidence_shape(self):
        module = self._load_llm_service_module("llm_service_calendar_news_boolean_shape_test")

        class BooleanShapeProvider(module.BaseLLMProvider):
            def chat(self, messages, model, temperature, max_tokens, timeout):
                return json.dumps(
                    {
                        "matched": True,
                        "evidence_index": True,
                        "confidence": True,
                        "match_reason": "布尔字段不是合格结构",
                        "classification_hint": "政策催化",
                        "policy_evidence": True,
                    },
                    ensure_ascii=False,
                )

        module.reset_llm_service()
        service = module.LLMService(timeout=3)
        service.provider = BooleanShapeProvider()

        result = service.adjudicate_calendar_event_news_evidence(
            {"title": "量子安全技术大会将于6月5日举办", "date": "2026-06-05"},
            [
                {"title": "候选1", "evidence_text": "同日候选1。", "source_date": "2026-06-05"},
                {"title": "候选2", "evidence_text": "同日候选2。", "source_date": "2026-06-05"},
            ],
            report_date="2026-06-05",
        )

        self.assertTrue(result["matched"])
        self.assertEqual(result["evidence_index"], -1)
        self.assertEqual(result["confidence"], "")

    def test_event_analysis_cache_uses_postgres_runtime_cache_when_configured(self):
        module = self._load_llm_service_module("llm_service_event_cache_test")

        class StubService:
            def __init__(self):
                self.entries = {}
                self.saved = []

            def is_postgres_backed(self):
                return True

            def get_runtime_cache_entry(self, namespace, cache_key, target_date):
                return self.entries.get((namespace, cache_key, target_date))

            def set_runtime_cache_entry(self, namespace, cache_key, target_date, payload, *, source="", ttl_seconds=None):
                self.saved.append((namespace, cache_key, target_date, payload, source, ttl_seconds))
                self.entries[(namespace, cache_key, target_date)] = {
                    "payload": dict(payload),
                    "source": source,
                }
                return True

        service = StubService()

        class StubDatabaseService:
            @classmethod
            def from_environment(cls):
                return service

        with tempfile.TemporaryDirectory() as tmp_dir, patch.object(
            module,
            "DatabaseService",
            StubDatabaseService,
            create=True,
        ), patch.dict(
            os.environ,
            {"A_DAILY_REPORT_DATABASE_URL": "postgresql://unit/report"},
            clear=True,
        ):
            cache = module.EventAnalysisCache(cache_file=str(Path(tmp_dir) / "event_analysis_cache.json"))
            cache.set("重大事件", {"main_direction": "半导体", "confidence": "高"})
            result = cache.get("重大事件")

        self.assertEqual(result, {"main_direction": "半导体", "confidence": "高"})
        self.assertEqual(service.saved[0][0], "llm_event_analysis")
        self.assertEqual(service.saved[0][1], cache._make_key("重大事件"))
        self.assertEqual(service.saved[0][3]["result"], {"main_direction": "半导体", "confidence": "高"})
        self.assertEqual(list(Path(tmp_dir).glob("*.json")), [])

    def test_event_analysis_cache_in_postgres_only_mode_does_not_write_local_json(self):
        module = self._load_llm_service_module("llm_service_event_cache_postgres_only_test")

        with tempfile.TemporaryDirectory() as tmp_dir, patch.dict(
            os.environ,
            {"A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME": "1"},
            clear=True,
        ):
            cache = module.EventAnalysisCache(cache_file=str(Path(tmp_dir) / "event_analysis_cache.json"))
            cache.set("重大事件", {"main_direction": "半导体", "confidence": "高"})
            result = cache.get("重大事件")

        self.assertEqual(result, {"main_direction": "半导体", "confidence": "高"})
        self.assertEqual(list(Path(tmp_dir).glob("*.json")), [])


if __name__ == "__main__":
    unittest.main()
