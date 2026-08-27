#!/usr/bin/env python3
"""Build a deterministic, explicitly non-flashable firmware-analysis handoff."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "analysis/BUG_LEDGER.md",
    "analysis/COMPLETION_AUDIT.md",
    "analysis/LOCAL_SOURCE_SEARCH_20260723.md",
    "analysis/REVERSE_ENGINEERING.md",
    "analysis/SOURCE_AND_RECOVERY_REQUEST.md",
    "analysis/TEST_CYCLES.md",
    "analysis/WORKSPACE_SOURCE_SEARCH_20260723.md",
    "analysis/binary_patch_spec.json",
    "analysis/binary_patch_verification.json",
    "analysis/firmware_report.json",
    "analysis/g6_readonly_probe_20260723.json",
    "analysis/product_contract.json",
    "analysis/release_audit.json",
    "tools/audit_release.py",
    "tools/inspect_firmware.py",
    "tools/probe_g6_readonly.py",
    "tools/verify_patch_spec.py",
    "tests/test_patch_spec.py",
    "tests/test_readonly_probe.py",
    "tests/test_release_audit.py",
]
FORBIDDEN_SUFFIXES = {".bin", ".hex", ".uf2", ".pem", ".key"}
ZIP_TIMESTAMP = (2026, 7, 23, 0, 0, 0)


def add_bytes(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, data)


def build(output: Path) -> dict[str, object]:
    missing = [name for name in FILES if not (ROOT / name).is_file()]
    if missing:
        raise FileNotFoundError("missing handoff file(s): " + ", ".join(missing))
    forbidden = [
        name for name in FILES if Path(name).suffix.lower() in FORBIDDEN_SUFFIXES
    ]
    if forbidden:
        raise ValueError("flashable/secret material forbidden: " + ", ".join(forbidden))

    entries = []
    payloads: list[tuple[str, bytes]] = []
    for name in FILES:
        data = (ROOT / name).read_bytes()
        payloads.append((name, data))
        entries.append(
            {
                "path": name,
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    manifest = {
        "package": "G6 HE firmware repair handoff",
        "date": "2026-07-23",
        "flashable": False,
        "contains_firmware_images": False,
        "purpose": "analysis, reproducible audit and supplier/source handoff only",
        "entries": entries,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w") as archive:
        add_bytes(
            archive,
            "HANDOFF_MANIFEST.json",
            (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode(),
        )
        for name, data in payloads:
            add_bytes(archive, name, data)

    archive_bytes = output.read_bytes()
    return {
        "output": str(output.resolve()),
        "size": len(archive_bytes),
        "sha256": hashlib.sha256(archive_bytes).hexdigest(),
        "entries": len(payloads) + 1,
        "flashable": False,
        "contains_firmware_images": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = build(args.output)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
