from __future__ import annotations

import base64
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from asset_pipeline.pipeline_tool import describe
from asset_pipeline.services.runner_service import process_source
from asset_pipeline.tests.fixtures.synthetic_spritesheet import synthetic_spritesheet


class RunnerIntegrationTests(unittest.TestCase):
    def test_describe_then_process_synthetic_spritesheet(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources = root / "sources"
            exports = root / "exports"
            sources.mkdir()
            Image.fromarray(synthetic_spritesheet(), mode="RGB").save(sources / "synthetic.png")
            capabilities = describe()

            with (
                patch("asset_pipeline.services.storage_service.SOURCES_DIR", sources),
                patch("asset_pipeline.services.storage_service.EXPORTS_DIR", exports),
                patch.dict(os.environ, {"ASSET_PIPELINE_PREVIEW_STORAGE": "memory"}),
            ):
                result = process_source(
                    "synthetic.png",
                    "integration-test",
                    {
                        "profile": "outline",
                        "cropPadding": 0,
                        "framePadding": 2,
                        "minFrameArea": 100,
                        "alphaCutoff": 10,
                        "upscaleMode": "none",
                    },
                    "greenscreen-clean",
                )

        self.assertTrue(capabilities["pipelines"])
        self.assertTrue(capabilities["stageRegistry"])
        self.assertEqual(result["source"], "synthetic.png")
        self.assertEqual(result["pipelineId"], "greenscreen-clean")
        self.assertEqual(len(result["frames"]), 2)
        preview_files = set(result["previewFileData"])
        self.assertTrue({"source.png", "processed.png", "alpha.png", "sheet.png"} <= preview_files)
        decoded = base64.b64decode(result["previewFileData"]["sheet.png"])
        self.assertTrue(decoded.startswith(b"\x89PNG\r\n\x1a\n"))


if __name__ == "__main__":
    unittest.main()
