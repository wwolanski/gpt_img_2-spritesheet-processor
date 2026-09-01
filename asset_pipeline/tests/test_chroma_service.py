from __future__ import annotations

import unittest


from asset_pipeline.services.chroma_service import greenscreen_alpha
from asset_pipeline.services.config import DEFAULT_OPTIONS
from asset_pipeline.tests.fixtures.synthetic_spritesheet import synthetic_spritesheet


class ChromaServiceTests(unittest.TestCase):
    def test_greenscreen_alpha_removes_border_and_keeps_foreground(self) -> None:
        rgb = synthetic_spritesheet()
        alpha, fields = greenscreen_alpha(rgb, (0, 255, 0), DEFAULT_OPTIONS)

        self.assertEqual(alpha.shape, rgb.shape[:2])
        self.assertEqual(int(alpha[0, 0]), 0)
        self.assertGreater(int(alpha[32, 24]), 200)
        self.assertGreater(int(alpha[34, 102]), 200)
        self.assertEqual(fields["rgb"].shape, rgb.shape)

    def test_green_screen_preserves_an_enclosed_region(self) -> None:
        rgb = synthetic_spritesheet()
        rgb[30:38, 25:32] = (0, 255, 0)

        alpha, _fields = greenscreen_alpha(rgb, (0, 255, 0), DEFAULT_OPTIONS)

        # The background detector intentionally only removes green connected
        # to the image border, so enclosed regions remain part of the sprite.
        self.assertGreater(int(alpha[33, 28]), 200)


if __name__ == "__main__":
    unittest.main()
