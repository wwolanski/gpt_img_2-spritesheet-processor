from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from asset_pipeline.services import upscale_service


class UpscaleServiceTests(unittest.TestCase):
    def tearDown(self) -> None:
        upscale_service.clear_aura_model_cache()

    def test_aura_model_is_cached_per_model_name(self) -> None:
        calls: list[str] = []

        class FakeAura:
            @classmethod
            def from_pretrained(cls, model_name: str) -> "FakeAura":
                calls.append(model_name)
                return cls()

            def upscale_4x_overlapped(self, image: Image.Image) -> Image.Image:
                return image.resize((image.width * 4, image.height * 4), Image.Resampling.NEAREST)

        fake_module = types.SimpleNamespace(AuraSR=FakeAura)
        rgba = np.zeros((2, 3, 4), dtype=np.uint8)
        rgba[:, :, :3] = (20, 30, 40)
        rgba[:, :, 3] = 255

        with patch.dict(sys.modules, {"aura_sr": fake_module}):
            first = upscale_service.upscale_rgba(rgba, "aura-sr", "test-model")
            second = upscale_service.upscale_rgba(rgba, "aura-sr", "test-model")

        self.assertEqual(calls, ["test-model"])
        self.assertEqual(first.shape, (8, 12, 4))
        self.assertTrue(np.array_equal(first, second))

    def test_aura_availability_uses_local_package_discovery(self) -> None:
        with patch("asset_pipeline.services.capabilities.importlib.util.find_spec", return_value=None):
            from asset_pipeline.services.capabilities import aura_sr_installed

            self.assertFalse(aura_sr_installed())


if __name__ == "__main__":
    unittest.main()
