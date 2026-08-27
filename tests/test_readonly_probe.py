from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import probe_g6_config_readonly as probe  # noqa: E402


class ReadOnlyProbePolicyTests(unittest.TestCase):
    def test_only_known_read_commands_are_used(self) -> None:
        self.assertEqual(
            (probe.LONG_OUTPUT_REPORT_ID, probe.LONG_INPUT_REPORT_ID),
            (0xB3, 0xB4),
        )
        self.assertEqual(
            (probe.SHORT_OUTPUT_REPORT_ID, probe.SHORT_INPUT_REPORT_ID),
            (0xB5, 0xB6),
        )

    def test_target_is_exact_g6_configuration_interface(self) -> None:
        self.assertEqual((probe.VID, probe.PID), (0x3434, 0xD086))
        self.assertEqual((probe.USAGE_PAGE, probe.USAGE), (0xFFC1, 1))

    def test_decoders_match_captured_responses(self) -> None:
        version = bytes.fromhex(
            "0407312e302e302b350000000000000000000000000656656e646f72"
            "000000000000000000000000000000000000000000000000000000000000000000"
        )
        self.assertEqual(probe.decode_version(version), "1.0.0+5")


if __name__ == "__main__":
    unittest.main()
