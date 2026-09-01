from __future__ import annotations

import unittest

import numpy as np

from asset_pipeline.services.frame_service import build_normalized_sheet, detect_frames


class FrameServiceTests(unittest.TestCase):
    def test_detect_frames_orders_components_left_to_right(self) -> None:
        alpha = np.zeros((64, 140), dtype=np.uint8)
        alpha[12:44, 8:36] = 255
        alpha[16:48, 82:116] = 255

        frames = detect_frames(alpha, min_frame_area=100, alpha_cutoff=10)

        self.assertEqual(len(frames), 2)
        self.assertEqual([frame.index for frame in frames], [0, 1])
        self.assertLess(frames[0].x, frames[1].x)
        self.assertEqual((frames[0].width, frames[0].height), (28, 32))

    def test_normalized_sheet_keeps_one_canvas_per_frame(self) -> None:
        alpha = np.zeros((64, 140), dtype=np.uint8)
        alpha[12:44, 8:36] = 255
        alpha[16:48, 82:116] = 255
        rgba = np.zeros((64, 140, 4), dtype=np.uint8)
        rgba[:, :, :3] = (200, 40, 40)
        rgba[:, :, 3] = alpha
        frames = detect_frames(alpha, min_frame_area=100, alpha_cutoff=10)

        sheet, metadata, size = build_normalized_sheet(rgba, frames, frame_padding=2)

        self.assertEqual(len(metadata), 2)
        self.assertEqual(sheet.shape, (size["height"], size["width"] * 2, 4))
        self.assertGreater(int(sheet[:, : size["width"], 3].sum()), 0)
        self.assertGreater(int(sheet[:, size["width"] :, 3].sum()), 0)


if __name__ == "__main__":
    unittest.main()
