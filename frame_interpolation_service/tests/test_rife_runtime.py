from __future__ import annotations

import unittest
import importlib.util
from unittest.mock import patch

import numpy as np

from app.rife_runtime import RifeRuntime, interpolate_pair, pad_tensor


class RifeRuntimeTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("torch"), "torch is an optional RIFE dependency")
    def test_padding_uses_model_required_128_grid(self) -> None:
        import torch

        tensor = torch.zeros((1, 3, 312, 262))
        padded, height, width = pad_tensor(tensor)
        self.assertEqual((height, width), (312, 262))
        self.assertEqual(tuple(padded.shape[-2:]), (384, 384))

    def test_midpoint_keeps_transparency_and_neutral_hidden_rgb(self) -> None:
        left = np.zeros((2, 2, 4), dtype=np.uint8)
        right = np.zeros((2, 2, 4), dtype=np.uint8)
        left[0, 0] = (0, 0, 0, 255)
        right[0, 1] = (0, 0, 0, 255)

        def fake_infer(_runtime, first, second, _scale):
            return np.rint((first.astype(np.float32) + second.astype(np.float32)) * 0.5).astype(np.uint8)

        runtime = RifeRuntime(model_path=None, device="cpu", half=False, model=object())  # type: ignore[arg-type]
        with patch("app.rife_runtime.infer_rgb", side_effect=fake_infer):
            output = interpolate_pair(runtime, left, right, (128, 128, 128), "rife", 1.0)
        self.assertEqual(output.shape, (2, 2, 4))
        self.assertEqual(tuple(output[1, 1, :3]), (128, 128, 128))
        self.assertEqual(int(output[1, 1, 3]), 0)


if __name__ == "__main__":
    unittest.main()
