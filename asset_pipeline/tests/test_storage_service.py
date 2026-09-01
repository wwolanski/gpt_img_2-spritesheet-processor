from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from asset_pipeline.services.errors import AssetPipelineError
from asset_pipeline.services.storage_service import safe_source_path
from asset_pipeline.services import storage_service


class StorageServiceTests(unittest.TestCase):
    def test_source_path_stays_inside_sources_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            sources = Path(temporary) / "sources"
            sources.mkdir()
            source = sources / "sprite.png"
            source.touch()

            with patch("asset_pipeline.services.storage_service.SOURCES_DIR", sources):
                self.assertEqual(safe_source_path("sprite.png"), source.resolve())
                with self.assertRaises(FileNotFoundError):
                    safe_source_path("../sprite.png")

    def test_missing_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            sources = Path(temporary) / "sources"
            sources.mkdir()
            with patch("asset_pipeline.services.storage_service.SOURCES_DIR", sources):
                with self.assertRaises(FileNotFoundError):
                    safe_source_path("missing.png")

    def test_export_does_not_replace_existing_target_without_explicit_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            preview = root / "previews" / "preview-1"
            preview.mkdir(parents=True)
            (preview / "metadata.json").write_text("{}", encoding="utf-8")
            (preview / "processed.png").write_bytes(b"new")
            exports = root / "exports"
            public = root / "public"
            existing = exports / "demo"
            existing.mkdir(parents=True)
            (existing / "keep.txt").write_text("keep", encoding="utf-8")

            with (
                patch.object(storage_service, "preview_dir_for", return_value=preview),
                patch.object(storage_service, "EXPORTS_DIR", exports),
                patch.object(storage_service, "PUBLIC_ASSETS_DIR", public),
            ):
                with self.assertRaisesRegex(AssetPipelineError, "already exists"):
                    storage_service.export_preview("preview-1", "demo")
                self.assertTrue((existing / "keep.txt").exists())

                storage_service.export_preview("preview-1", "demo", overwrite=True)
                self.assertFalse((existing / "keep.txt").exists())
                self.assertEqual((existing / "processed.png").read_bytes(), b"new")


if __name__ == "__main__":
    unittest.main()
