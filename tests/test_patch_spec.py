from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from verify_patch_spec import verify  # noqa: E402


MOUSE = Path(
    "<G6_FIRMWARE_DIR>/G6HE_v1.0.0+5_20260722.signed.bin"
)
SPEC = ROOT / "analysis/binary_patch_spec.json"


@unittest.skipUnless(MOUSE.exists(), "mouse firmware unavailable")
class BinaryPatchSpecTests(unittest.TestCase):
    def test_patch_spec_matches_exact_original_without_modifying_it(self) -> None:
        report = verify(MOUSE, SPEC)
        self.assertTrue(report["all_passed"])
        self.assertEqual(report["checks_passed"], 4)
        self.assertEqual(report["checks_total"], 4)
        self.assertFalse(report["image_modified"])
        self.assertFalse(report["safe_to_flash"])


if __name__ == "__main__":
    unittest.main()
