from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import numpy as np

from asset_pipeline.services.interpolation_client import (
    interpolate_sequence,
    normalized_rgba_frames,
    remap_edit_frames,
    remap_editor_part_frames,
    remap_grounding_frames,
    sequence_from_rgba,
)
from asset_pipeline.services.models import FrameBox
from asset_pipeline.services.semantic_models import FrameSequence, SemanticGrounding, SemanticPartSpec


class InterpolationClientTests(unittest.TestCase):
    def sequence(self) -> FrameSequence:
        final = np.zeros((2, 2, 4), dtype=np.uint8)
        final[:, :, :3] = (10, 20, 30)
        final[:, :, 3] = 255
        return FrameSequence(
            raw_rgb_frames=[final[:, :, :3]],
            base_alpha_frames=[final[:, :, 3]],
            semantic_alpha_frames=[np.pad(final[:, :, 3], ((1, 1), (1, 1)))],
            sam_rgb_frames=[np.full((4, 4, 3), 128, dtype=np.uint8)],
            final_rgba_frames=[final],
            boxes=[FrameBox(0, 0, 0, 2, 2, 4, 1, 1)],
            semantic_offsets=[(1, 1)],
            key_color=(0, 255, 0),
        )

    def test_normalizes_rgba_into_semantic_canvas(self) -> None:
        frames = normalized_rgba_frames(self.sequence())
        self.assertEqual(frames[0].shape, (4, 4, 4))
        np.testing.assert_array_equal(frames[0][1:3, 1:3, :3], np.full((2, 2, 3), (10, 20, 30)))
        self.assertEqual(int(frames[0][:, :, 3].sum()), 4 * 255)

    def test_interpolated_sequence_uses_direct_canvas_coordinates(self) -> None:
        source = self.sequence()
        frames = normalized_rgba_frames(source) * 2
        output = sequence_from_rgba(source, frames)
        self.assertEqual(len(output.sam_rgb_frames), 2)
        self.assertEqual(output.semantic_offsets, [(0, 0), (0, 0)])
        self.assertEqual(output.boxes[1].index, 1)
        self.assertEqual(output.boxes[1].width, 4)

    def test_qwen_grounding_maps_source_frames_to_even_output_frames(self) -> None:
        spec = SemanticPartSpec(
            "weapon",
            "weapon",
            "hammer",
            "high",
            "always",
            [SemanticGrounding(3, (1, 2, 3, 4), (2, 3), 0.9)],
        )
        remap_grounding_frames([spec])
        self.assertEqual(spec.grounding[0].frame, 6)

    def test_legacy_preset_edits_map_to_even_output_frames(self) -> None:
        edits = [{"frame": 3, "type": "positive_point", "x": 10, "y": 20}]
        self.assertEqual(remap_edit_frames(edits, 8)[0]["frame"], 6)

    def test_new_interpolated_edits_are_not_remapped_twice(self) -> None:
        edits = [
            {
                "frame": 3,
                "type": "positive_point",
                "x": 10,
                "y": 20,
                "space": {"frameCount": 16, "frameInterpolationFactor": 2},
            }
        ]
        self.assertEqual(remap_edit_frames(edits, 8)[0]["frame"], 3)

    def test_editor_part_edits_use_source_timebase_migration(self) -> None:
        parts = [{"id": "sword", "edits": [{"frame": 7, "type": "bbox", "box": [1, 2, 3, 4]}]}]
        self.assertEqual(remap_editor_part_frames(parts, 8)[0]["edits"][0]["frame"], 14)

    def test_service_response_doubles_loop_sequence(self) -> None:
        source = self.sequence()
        source.raw_rgb_frames *= 2
        source.base_alpha_frames *= 2
        source.semantic_alpha_frames *= 2
        source.sam_rgb_frames *= 2
        source.final_rgba_frames *= 2
        source.boxes *= 2
        source.semantic_offsets *= 2

        class Response:
            def __init__(self, body: bytes):
                self.body = body

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self) -> bytes:
                return self.body

        def fake_urlopen(request, timeout):
            self.assertGreater(timeout, 0)
            payload = json.loads(request.data.decode("utf-8"))
            frames = payload["frames"]
            output = []
            for index, frame in enumerate(frames):
                output.append({"rgbaPngBase64": frame["rgbaPngBase64"]})
                output.append({"rgbaPngBase64": frame["rgbaPngBase64"]})
            return Response(json.dumps({"frames": output}).encode("utf-8"))

        warnings: list[str] = []
        with patch("asset_pipeline.services.interpolation_client.urllib.request.urlopen", side_effect=fake_urlopen):
            result = interpolate_sequence(source, warnings)
        self.assertTrue(result.enabled)
        self.assertEqual(result.source_frame_count, 2)
        self.assertEqual(result.output_frame_count, 4)
        self.assertEqual(len(result.sequence.final_rgba_frames), 4)
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
