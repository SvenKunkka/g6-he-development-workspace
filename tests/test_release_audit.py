from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from audit_release import SHARED_KEYHASH, audit  # noqa: E402
from inspect_firmware import parse_image  # noqa: E402


MOUSE = Path(
    "<G6_FIRMWARE_DIR>/G6HE_v1.0.0+5_20260722.signed.bin"
)
RECEIVER = Path(
    "<G6_FIRMWARE_DIR>/"
    "UltraLink_dongle_rx21_v1.2.1_1_20260721.signed.bin"
)
CONTRACT = ROOT / "analysis/product_contract.json"
SNAPSHOT = ROOT / "analysis/connected_devices.json"
RUNTIME_PROBE = ROOT / "analysis/g6_readonly_probe_20260723.json"


@unittest.skipUnless(MOUSE.exists() and RECEIVER.exists(), "firmware images unavailable")
class FirmwareImageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mouse = parse_image(MOUSE)
        cls.receiver = parse_image(RECEIVER)
        cls.report = audit(MOUSE, RECEIVER, CONTRACT, SNAPSHOT, RUNTIME_PROBE)

    def test_exact_known_hashes(self) -> None:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(
            self.mouse["hashes"]["sha256"], contract["mouse"]["sha256"]
        )
        self.assertEqual(
            self.receiver["hashes"]["sha256"], contract["receiver"]["sha256"]
        )

    def test_both_images_have_valid_layout_and_internal_hash(self) -> None:
        for report in (self.mouse, self.receiver):
            self.assertEqual(report["errors"], [])
            self.assertTrue(report["layout"]["exact_file_length"])
            self.assertTrue(report["sha512_tlv_matches"])

    def test_vector_tables_are_plausible_thumb_entries(self) -> None:
        for report in (self.mouse, self.receiver):
            self.assertTrue(report["vector_table"]["thumb_reset_handler"])
            self.assertTrue(report["vector_table"]["reset_handler_inside_body"])
            self.assertGreater(report["vector_table"]["initial_sp"], 0x20000000)
        self.assertEqual(
            self.mouse["vector_table"]["runtime_payload_address"], 0x20001000
        )
        self.assertEqual(
            self.mouse["vector_table"]["reset_handler_body_offset"], 0x1F0BC
        )

    def test_pair_uses_expected_shared_keyhash(self) -> None:
        keyhashes = []
        for report in (self.mouse, self.receiver):
            keyhashes.append(
                next(x["value_hex"] for x in report["tlvs"] if x["type"] == 0x01)
            )
        self.assertEqual(keyhashes, [SHARED_KEYHASH, SHARED_KEYHASH])

    def test_missing_rollback_and_dependency_metadata_is_detected(self) -> None:
        ids = {issue["id"] for issue in self.report["issues"]}
        self.assertIn("B-01", ids)
        self.assertIn("B-02", ids)

    def test_null_bond_key_and_sensitive_logs_are_detected(self) -> None:
        issues = {issue["id"]: issue for issue in self.report["issues"]}
        self.assertIn("B-03", issues)
        self.assertIn("B-04", issues)
        self.assertIn("[322499]", issues["B-03"]["evidence"][0])
        self.assertIn(
            "[99232, 99312, 100178]", issues["B-04"]["evidence"][0]
        )

    def test_product_launcher_mismatches_are_detected(self) -> None:
        issues = {issue["id"]: issue for issue in self.report["issues"]}
        self.assertIn("B-07", issues)
        self.assertIn("B-08", issues)
        self.assertEqual(
            issues["B-08"]["status"], "confirmed-binary-profile-drift"
        )
        self.assertTrue(
            any("0x200158C0" in item for item in issues["B-08"]["evidence"])
        )

    def test_mouse_serial_check_targets_exact_vid_pid(self) -> None:
        issues = {issue["id"]: issue for issue in self.report["issues"]}
        self.assertIn("B-09", issues)
        self.assertIn("3434:D086", issues["B-09"]["evidence"][0])

    def test_defect_ids_are_unique(self) -> None:
        ids = [issue["id"] for issue in self.report["issues"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_audit_does_not_claim_a_burnable_fixed_image(self) -> None:
        self.assertFalse(self.report["images_modified"])
        self.assertFalse(self.report["burnable_fixed_firmware_ready"])
        self.assertGreaterEqual(len(self.report["build_blockers"]), 4)

    def test_non_fault_stall_resilience_gap_is_tracked(self) -> None:
        issues = {issue["id"]: issue for issue in self.report["issues"]}
        self.assertEqual(
            issues["B-13"]["status"], "high-confidence-resilience-gap"
        )
        self.assertTrue(
            any("SYSRESETREQ" in item for item in issues["B-13"]["evidence"])
        )

    def test_runtime_input_path_stall_is_tracked(self) -> None:
        issues = {issue["id"]: issue for issue in self.report["issues"]}
        self.assertEqual(
            issues["B-11"]["status"],
            "runtime-observed-input-path-stall",
        )
        self.assertTrue(
            any("B3/B4" in item for item in issues["B-11"]["evidence"])
        )


if __name__ == "__main__":
    unittest.main()
