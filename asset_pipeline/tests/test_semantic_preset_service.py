from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import asset_pipeline.services.semantic_preset_service as preset_service

DEFAULT_PRESETS_FILE = preset_service.SEMANTIC_PRESETS_FILE
DEFAULT_EXAMPLE_FILE = preset_service.SEMANTIC_PRESETS_EXAMPLE_FILE


class SemanticPresetServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.runtime_file = root / ".runtime" / "semantic_editor_presets.json"
        self.legacy_file = root / "config" / "semantic_editor_presets.json"
        self.lock_file = self.runtime_file.with_name("semantic_editor_presets.json.lock")
        self.constants = patch.multiple(
            preset_service,
            SEMANTIC_PRESETS_FILE=self.runtime_file,
            SEMANTIC_PRESETS_LEGACY_FILE=self.legacy_file,
            SEMANTIC_PRESETS_LOCK_FILE=self.lock_file,
        )
        self.constants.start()
        self.addCleanup(self.constants.stop)
        self.addCleanup(self.temp_dir.cleanup)

    def test_default_storage_is_runtime_and_example_is_separate(self) -> None:
        self.assertEqual(DEFAULT_PRESETS_FILE.parent.name, ".runtime")
        self.assertEqual(DEFAULT_PRESETS_FILE.name, "semantic_editor_presets.json")
        self.assertEqual(DEFAULT_EXAMPLE_FILE.name, "semantic_editor_presets.example.json")
        self.assertNotEqual(DEFAULT_EXAMPLE_FILE, DEFAULT_PRESETS_FILE)

    def test_save_writes_versioned_data_to_runtime_path(self) -> None:
        result = preset_service.save_semantic_preset(
            "  Wing   edits ",
            {"semanticInputMode": "not-a-mode", "semanticEditorParts": "invalid"},
        )

        self.assertTrue(self.runtime_file.exists())
        self.assertFalse(self.legacy_file.exists())
        payload = json.loads(self.runtime_file.read_text(encoding="utf-8"))
        self.assertEqual(payload["version"], 2)
        self.assertEqual(payload["presets"], result["presets"])
        self.assertEqual(payload["presets"][0]["name"], "Wing edits")
        self.assertEqual(payload["presets"][0]["settings"]["semanticInputMode"], "neutral_matte")
        self.assertEqual(list(self.runtime_file.parent.glob(".*.tmp")), [])

    def test_legacy_file_and_version_one_are_migrated_to_runtime(self) -> None:
        self.legacy_file.parent.mkdir(parents=True)
        self.legacy_file.write_text(
            json.dumps(
                {
                    "version": 1,
                    "presets": [
                        {
                            "name": "legacy preset",
                            "settings": {"semanticGroundingMinConfidence": 0.6},
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = preset_service.list_semantic_presets()

        self.assertEqual(result["presets"][0]["name"], "legacy preset")
        self.assertTrue(self.runtime_file.exists())
        self.assertTrue(self.legacy_file.exists())
        migrated = json.loads(self.runtime_file.read_text(encoding="utf-8"))
        self.assertEqual(migrated["version"], 2)
        self.assertEqual(migrated["presets"][0]["settings"]["semanticGroundingMinConfidence"], 0.6)

    def test_future_version_is_not_overwritten(self) -> None:
        self.runtime_file.parent.mkdir(parents=True)
        original = {"version": 99, "presets": []}
        self.runtime_file.write_text(json.dumps(original), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "Unsupported semantic preset version"):
            preset_service.list_semantic_presets()

        self.assertEqual(json.loads(self.runtime_file.read_text(encoding="utf-8")), original)

    def test_atomic_write_removes_temporary_file_after_replace_failure(self) -> None:
        self.runtime_file.parent.mkdir(parents=True)
        with patch.object(preset_service.os, "replace", side_effect=OSError("replace failed")):
            with self.assertRaisesRegex(OSError, "replace failed"):
                preset_service._write_preset_file({"version": 2, "presets": []})

        self.assertEqual(list(self.runtime_file.parent.glob(".*.tmp")), [])

    @unittest.skipUnless(os.name == "posix", "fcntl-based lock test requires POSIX")
    def test_lock_serializes_writers_across_processes(self) -> None:
        script = """
import sys
import time
from pathlib import Path
import asset_pipeline.services.semantic_preset_service as service

service.SEMANTIC_PRESETS_LOCK_FILE = Path(sys.argv[1])
with service._preset_lock():
    print("locked", flush=True)
    time.sleep(0.35)
"""
        child = subprocess.Popen(
            [sys.executable, "-c", script, str(self.lock_file)],
            cwd=Path(__file__).resolve().parents[2],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            self.assertEqual(child.stdout.readline().strip(), "locked")
            started_waiting = time.monotonic()
            with preset_service._preset_lock():
                pass
            elapsed = time.monotonic() - started_waiting
            self.assertGreaterEqual(elapsed, 0.25)
        finally:
            child.wait(timeout=2)
            child_error = child.stderr.read()
            child.stdout.close()
            child.stderr.close()
            if child.returncode != 0:
                self.fail(child_error)


if __name__ == "__main__":
    unittest.main()
