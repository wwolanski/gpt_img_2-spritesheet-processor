import os
import unittest
from unittest.mock import patch

from asset_pipeline.services.semantic_client import qwen_base_url
from semantic_client.config import load_config
from semantic_client.qwen3_vl import cache_dir, cache_enabled, strict_config_cache_key


class SemanticClientConfigTests(unittest.TestCase):
    def test_current_environment_variables_are_loaded(self) -> None:
        values = {
            "SEMANTIC_CLIENT_QWEN_BASE_URL": "http://current.example/v1",
            "SEMANTIC_CLIENT_QWEN_API_KEY": "current-key",
            "SEMANTIC_CLIENT_QWEN_MODEL": "current-model",
            "SEMANTIC_CLIENT_QWEN_MODEL_AUTO": "current-pattern",
            "SEMANTIC_CLIENT_QWEN_TIMEOUT_SECONDS": "42",
            "SEMANTIC_CLIENT_QWEN_TEMPERATURE": "0.2",
            "SEMANTIC_CLIENT_QWEN_TOP_P": "0.7",
            "SEMANTIC_CLIENT_QWEN_MAX_TOKENS": "512",
            "SEMANTIC_CLIENT_QWEN_SEED": "9",
            "SEMANTIC_CLIENT_STRUCTURED_OUTPUT": "0",
            "SEMANTIC_CLIENT_ALLOW_JSON_OBJECT_FALLBACK": "1",
        }
        with patch.dict(os.environ, values, clear=True):
            config = load_config()

        self.assertEqual(config.base_url, "http://current.example/v1")
        self.assertEqual(config.api_key, "current-key")
        self.assertEqual(config.model, "current-model")
        self.assertEqual(config.model_auto_pattern, "current-pattern")
        self.assertEqual(config.timeout_seconds, 42.0)
        self.assertEqual(config.temperature, 0.2)
        self.assertEqual(config.top_p, 0.7)
        self.assertEqual(config.max_tokens, 512)
        self.assertEqual(config.seed, 9)
        self.assertFalse(config.use_structured_output)
        self.assertTrue(config.allow_json_object_fallback)

    def test_current_cache_environment_variables_are_loaded(self) -> None:
        values = {
            "SEMANTIC_CLIENT_QWEN_CACHE": "0",
            "SEMANTIC_CLIENT_QWEN_CACHE_DIR": "/tmp/current-semantic-cache",
            "SEMANTIC_CLIENT_QWEN_CACHE_STRICT_CONFIG": "1",
        }
        with patch.dict(os.environ, values, clear=True):
            self.assertFalse(cache_enabled())
            self.assertEqual(str(cache_dir()), "/tmp/current-semantic-cache")
            self.assertTrue(strict_config_cache_key())

    def test_pipeline_metadata_uses_current_qwen_url(self) -> None:
        values = {"SEMANTIC_CLIENT_QWEN_BASE_URL": "http://current.example/v1"}
        with patch.dict(os.environ, values, clear=True):
            self.assertEqual(qwen_base_url(), "http://current.example/v1")


if __name__ == "__main__":
    unittest.main()
