#!/usr/bin/env python3
"""Verify a binary patch specification without modifying the target image."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any


def verify(image_path: Path, spec_path: Path) -> dict[str, Any]:
    image = image_path.read_bytes()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(image).hexdigest()
    checks: list[dict[str, Any]] = [
        {
            "id": "target.sha256",
            "pass": digest == spec["target"]["sha256"],
            "actual": digest,
            "expected": spec["target"]["sha256"],
        }
    ]
    header_size = int(spec["target"]["header_size"])
    runtime_payload = int(spec["target"]["runtime_payload_address"], 16)

    for patch in spec["patches"]:
        file_offset = int(patch["signed_file_offset"], 16)
        body_offset = int(patch["body_offset"], 16)
        original = bytes.fromhex(patch["original_bytes_hex"])
        replacement = bytes.fromhex(patch["replacement_bytes_hex"])
        checks.extend(
            [
                {
                    "id": f"{patch['id']}.offset_relation",
                    "pass": file_offset == header_size + body_offset,
                    "actual": file_offset,
                    "expected": header_size + body_offset,
                },
                {
                    "id": f"{patch['id']}.original_bytes",
                    "pass": image[file_offset : file_offset + len(original)]
                    == original,
                    "actual": image[
                        file_offset : file_offset + len(original)
                    ].hex(),
                    "expected": original.hex(),
                },
            ]
        )
        if len(replacement) == 4:
            pointer = struct.unpack("<I", replacement)[0]
            target_body_offset = pointer - runtime_payload
            target_file_offset = header_size + target_body_offset
            string_end = image.find(b"\0", target_file_offset)
            pointed_string = (
                image[target_file_offset:string_end].decode("ascii", "replace")
                if target_file_offset >= header_size and string_end >= 0
                else None
            )
            checks.append(
                {
                    "id": f"{patch['id']}.replacement_target",
                    "pass": pointed_string
                    == patch["replacement_points_to_existing_string"],
                    "actual": pointed_string,
                    "expected": patch["replacement_points_to_existing_string"],
                }
            )

    return {
        "image": str(image_path.resolve()),
        "spec": str(spec_path.resolve()),
        "checks": checks,
        "checks_passed": sum(bool(item["pass"]) for item in checks),
        "checks_total": len(checks),
        "all_passed": all(bool(item["pass"]) for item in checks),
        "image_modified": False,
        "safe_to_flash": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify(args.image, args.spec)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
