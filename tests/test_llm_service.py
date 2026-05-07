import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class LlmServiceEnvTest(unittest.TestCase):
    def test_default_deepseek_model_uses_flash_when_env_is_missing(self):
        module_path = ROOT / "scripts" / "llm_service.py"
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_path = Path(tmp_dir) / ".env"
            env_path.write_text("IWENCAI_API_KEY=from-file\n", encoding="utf-8")

            original_model = os.environ.pop("DEEPSEEK_MODEL", None)
            try:
                with patch("pathlib.Path.cwd", return_value=Path(tmp_dir)):
                    spec = importlib.util.spec_from_file_location("llm_service_default_model_test", module_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                self.assertEqual(os.environ["DEEPSEEK_MODEL"], "deepseek-v4-flash")
            finally:
                if original_model is not None:
                    os.environ["DEEPSEEK_MODEL"] = original_model
                else:
                    os.environ.pop("DEEPSEEK_MODEL", None)

    def test_local_env_file_does_not_override_existing_environment(self):
        module_path = ROOT / "scripts" / "llm_service.py"
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
                        spec = importlib.util.spec_from_file_location("llm_service_env_test", module_path)
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)

                    self.assertEqual(os.environ["IWENCAI_API_KEY"], "from-shell")
                    self.assertEqual(os.environ["DEEPSEEK_MODEL"], "from-file-model")
                finally:
                    if original_model is not None:
                        os.environ["DEEPSEEK_MODEL"] = original_model
                    else:
                        os.environ.pop("DEEPSEEK_MODEL", None)


if __name__ == "__main__":
    unittest.main()
