import tempfile
import unittest
from pathlib import Path

from services.packaging_validation import (
    validate_frozen_layout,
    validate_source_package,
)


class PackagingValidationTests(unittest.TestCase):
    def test_current_source_package_manifest_is_valid(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(validate_source_package(root), [])

    def test_frozen_layout_reports_missing_required_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            package_dir = Path(directory)
            errors = validate_frozen_layout(package_dir)

        self.assertEqual(len(errors), 2)
        self.assertTrue(any("JARVIS.exe" in error for error in errors))
        self.assertTrue(any("curriculum.json" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
