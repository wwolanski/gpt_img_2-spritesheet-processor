from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from asset_pipeline.services.config import CONFIG_DIR, validate_config

REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_TOOL = REPO_ROOT / "asset_pipeline" / "pipeline_tool.py"


class ConfigValidationTests(unittest.TestCase):
    def test_tracked_configuration_is_valid(self) -> None:
        self.assertEqual(validate_config(), [])

    def test_validator_reports_pipeline_identity_and_stage_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config_dir = Path(temporary) / "config"
            shutil.copytree(CONFIG_DIR, config_dir)
            pipeline_path = config_dir / "pipelines" / "greenscreen-clean.json"
            data = json.loads(pipeline_path.read_text(encoding="utf-8"))
            data["id"] = "wrong-id"
            data["stages"] = data["stages"][1:]
            pipeline_path.write_text(json.dumps(data), encoding="utf-8")

            errors = validate_config(config_dir)

        self.assertTrue(any("id must match filename" in error for error in errors))
        self.assertTrue(any("missing stages" in error for error in errors))

    def test_validator_reports_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config_dir = Path(temporary) / "config"
            shutil.copytree(CONFIG_DIR, config_dir)
            (config_dir / "defaults.json").write_text("{broken", encoding="utf-8")

            errors = validate_config(config_dir)

        self.assertTrue(any("defaults.json: invalid JSON" in error for error in errors))

    def test_validator_reports_invalid_option_ranges(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config_dir = Path(temporary) / "config"
            shutil.copytree(CONFIG_DIR, config_dir)
            defaults_path = config_dir / "defaults.json"
            data = json.loads(defaults_path.read_text(encoding="utf-8"))
            data["defaultOptions"]["flowConfidenceFloor"] = 2
            data["defaultOptions"]["opaqueThreshold"] = 1
            data["defaultOptions"]["transparentThreshold"] = 10
            defaults_path.write_text(json.dumps(data), encoding="utf-8")

            errors = validate_config(config_dir)

        self.assertTrue(any("flowConfidenceFloor: must be between 0 and 1" in error for error in errors))
        self.assertTrue(any("opaqueThreshold must be greater than or equal" in error for error in errors))

    def test_validate_config_command_returns_machine_readable_success(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(PIPELINE_TOOL), "validate-config"],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["valid"], True)

    def test_cli_rejection_uses_standard_error_and_stderr_logging(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(PIPELINE_TOOL),
                "process",
                "--source",
                "../secret.png",
                "--preview-id",
                "test",
            ],
            cwd=REPO_ROOT,
            input="{}",
            check=False,
            capture_output=True,
            text=True,
        )

        payload = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(payload["ok"], False)
        self.assertEqual(payload["error"]["code"], "invalid_request")
        self.assertIn("WARNING asset_pipeline.cli", completed.stderr)

    def test_cli_rejects_invalid_option_ranges(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(PIPELINE_TOOL),
                "process",
                "--source",
                "pirate_outline.png",
                "--preview-id",
                "test",
            ],
            cwd=REPO_ROOT,
            input=json.dumps({"options": {"flowConfidenceFloor": 2}}),
            check=False,
            capture_output=True,
            text=True,
        )

        payload = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(payload["error"]["code"], "invalid_request")
        self.assertIn("flowConfidenceFloor", payload["error"]["details"]["errors"][0])


if __name__ == "__main__":
    unittest.main()
