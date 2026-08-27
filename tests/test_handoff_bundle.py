from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

import sys

sys.path.insert(0, str(ROOT / "tools"))
from build_handoff_bundle import build  # noqa: E402


class HandoffBundleTests(unittest.TestCase):
    def test_bundle_is_explicitly_non_flashable_and_contains_no_firmware(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "handoff_NOT_FLASHABLE.zip"
            report = build(output)
            self.assertFalse(report["flashable"])
            self.assertFalse(report["contains_firmware_images"])
            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()
                self.assertIn("HANDOFF_MANIFEST.json", names)
                self.assertIn("analysis/LOCAL_SOURCE_SEARCH_20260723.md", names)
                self.assertFalse(
                    any(
                        Path(name).suffix.lower()
                        in {".bin", ".hex", ".uf2", ".pem", ".key"}
                        for name in names
                    )
                )


if __name__ == "__main__":
    unittest.main()
