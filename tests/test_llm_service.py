import importlib.util
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


if __name__ == "__main__":
    unittest.main()
