from __future__ import annotations

import unittest

import numpy as np

from asset_pipeline.services.despill_service import neutralize_edge_spill, transparentize_edge_spill
from asset_pipeline.services.image_ops import rgb_hsv_fields


class DespillServiceTests(unittest.TestCase):
    def test_neutralize_reduces_green_spill_without_changing_none_mode(self) -> None:
        rgb = np.full((8, 8, 3), (100, 180, 60), dtype=np.uint8)
        alpha = np.full((8, 8), 255, dtype=np.uint8)
        fields = rgb_hsv_fields(rgb)

        cleaned = neutralize_edge_spill(rgb, alpha, fields, "gray", strength=1.0, darken=0.0)

        self.assertLess(int(cleaned[4, 4, 1]), int(rgb[4, 4, 1]))
        np.testing.assert_array_equal(neutralize_edge_spill(rgb, alpha, fields, "none", 1.0, 0.0), rgb)

    def test_transparentize_reduces_alpha_for_green_spill(self) -> None:
        rgb = np.full((8, 8, 3), (100, 180, 60), dtype=np.uint8)
        alpha = np.full((8, 8), 255, dtype=np.uint8)

        cleaned = transparentize_edge_spill(alpha, rgb_hsv_fields(rgb), strength=1.0)

        self.assertLess(int(cleaned[4, 4]), int(alpha[4, 4]))


if __name__ == "__main__":
    unittest.main()
