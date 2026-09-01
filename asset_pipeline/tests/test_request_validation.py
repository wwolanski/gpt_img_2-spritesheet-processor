from __future__ import annotations

import unittest

from asset_pipeline.services.request_validation import (
    validate_pipeline_ids,
    validate_source_name,
    validate_source_names,
    validate_workers,
)


class RequestValidationTests(unittest.TestCase):
    def test_source_must_be_a_supported_filename(self) -> None:
        self.assertEqual(validate_source_name("pirate_outline.png"), "pirate_outline.png")
        with self.assertRaises(ValueError):
            validate_source_name("../pirate_outline.png")
        with self.assertRaises(ValueError):
            validate_source_name("notes.txt")

    def test_source_list_has_bounds_and_no_duplicates(self) -> None:
        self.assertEqual(validate_source_names(["a.png", "b.webp"]), ["a.png", "b.webp"])
        with self.assertRaises(ValueError):
            validate_source_names(["a.png", "a.png"])

    def test_workers_are_bounded(self) -> None:
        self.assertEqual(validate_workers(4), 4)
        with self.assertRaises(ValueError):
            validate_workers(0)
        with self.assertRaises(ValueError):
            validate_workers(17)

    def test_pipeline_ids_are_strict(self) -> None:
        self.assertEqual(validate_pipeline_ids(["outline-ink"]), ["outline-ink"])
        with self.assertRaises(ValueError):
            validate_pipeline_ids(["outline-ink", "outline-ink"])
        with self.assertRaises(ValueError):
            validate_pipeline_ids(["outline-ink", 3])


if __name__ == "__main__":
    unittest.main()
