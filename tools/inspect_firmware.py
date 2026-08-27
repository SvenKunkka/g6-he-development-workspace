#!/usr/bin/env python3
"""Read-only inspector for MCUboot signed firmware images."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import struct
from collections import Counter
from pathlib import Path


IMAGE_MAGIC = 0x96F3B83D
TLV_INFO_MAGIC = 0x6907
TLV_NAMES = {
    0x01: "KEYHASH",
    0x02: "PUBKEY",
    0x10: "SHA256",
    0x11: "SHA384",
    0x12: "SHA512",
    0x20: "RSA2048_PSS",
    0x22: "ECDSA_SIG",
    0x23: "RSA3072_PSS",
    0x24: "ED25519",
    0x25: "SIG_PURE",
    0x40: "DEPENDENCY",
    0x50: "SECURITY_COUNTER",
}
FLAG_NAMES = {
    0x00000001: "PIC",
    0x00000004: "ENCRYPTED_AES128",
    0x00000008: "ENCRYPTED_AES256",
    0x00000010: "NON_BOOTABLE",
    0x00000020: "RAM_LOAD",
    0x00000100: "ROM_FIXED",
}


def shannon_entropy(block: bytes) -> float:
    if not block:
        return 0.0
    counts = Counter(block)
    return -sum((n / len(block)) * math.log2(n / len(block)) for n in counts.values())


def ascii_strings(data: bytes, minimum: int = 5) -> list[dict[str, object]]:
    pattern = re.compile(rb"[\x20-\x7e]{" + str(minimum).encode() + rb",}")
    return [
        {"offset": match.start(), "text": match.group().decode("ascii")}
        for match in pattern.finditer(data)
    ]


def parse_image(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    if len(data) < 32:
        raise ValueError(f"{path}: shorter than MCUboot header")

    (
        magic,
        load_addr,
        hdr_size,
        protected_tlv_size,
        img_size,
        flags,
        ver_major,
        ver_minor,
        ver_revision,
        ver_build,
        pad,
    ) = struct.unpack_from("<IIHHIIBBHII", data, 0)

    tlv_offset = hdr_size + img_size + protected_tlv_size
    errors: list[str] = []
    if magic != IMAGE_MAGIC:
        errors.append(f"unexpected image magic 0x{magic:08x}")
    if hdr_size < 32 or hdr_size > len(data):
        errors.append(f"invalid header size {hdr_size}")
    if tlv_offset + 4 > len(data):
        errors.append(f"TLV offset 0x{tlv_offset:x} outside file")

    tlvs: list[dict[str, object]] = []
    tlv_total = 0
    tlv_magic = None
    if not errors:
        tlv_magic, tlv_total = struct.unpack_from("<HH", data, tlv_offset)
        if tlv_magic != TLV_INFO_MAGIC:
            errors.append(f"unexpected TLV magic 0x{tlv_magic:04x}")
        if tlv_offset + tlv_total != len(data):
            errors.append(
                f"TLV length mismatch: end=0x{tlv_offset + tlv_total:x}, "
                f"file=0x{len(data):x}"
            )
        cursor = tlv_offset + 4
        tlv_end = min(tlv_offset + tlv_total, len(data))
        while cursor + 4 <= tlv_end:
            tlv_type, tlv_len = struct.unpack_from("<HH", data, cursor)
            value_start = cursor + 4
            value_end = value_start + tlv_len
            if value_end > tlv_end:
                errors.append(f"TLV 0x{tlv_type:04x} overruns TLV area")
                break
            tlvs.append(
                {
                    "offset": cursor,
                    "type": tlv_type,
                    "name": TLV_NAMES.get(tlv_type, f"UNKNOWN_0x{tlv_type:04x}"),
                    "length": tlv_len,
                    "value_hex": data[value_start:value_end].hex(),
                }
            )
            cursor = value_end
        if cursor != tlv_end:
            errors.append(f"{tlv_end - cursor} trailing byte(s) in TLV area")

    signed_region = data[:tlv_offset]
    hashes = {
        "sha256": hashlib.sha256(data).hexdigest(),
        "signed_region_sha512": hashlib.sha512(signed_region).hexdigest(),
    }
    hash_tlv = next((x for x in tlvs if x["type"] == 0x12), None)
    sha512_matches = bool(
        hash_tlv and hash_tlv["value_hex"] == hashes["signed_region_sha512"]
    )

    body = data[hdr_size : hdr_size + img_size]
    vector_words = list(struct.unpack_from("<16I", body, 0)) if len(body) >= 64 else []
    runtime_payload_address = load_addr + hdr_size
    reset_handler_address = (
        vector_words[1] & ~1 if len(vector_words) > 1 else None
    )
    reset_handler_body_offset = (
        reset_handler_address - runtime_payload_address
        if reset_handler_address is not None
        else None
    )
    core_vector_names = [
        "initial_sp",
        "reset",
        "nmi",
        "hard_fault",
        "mem_manage",
        "bus_fault",
        "usage_fault",
        "secure_fault",
        "reserved_8",
        "reserved_9",
        "reserved_10",
        "svc",
        "debug_monitor",
        "reserved_13",
        "pendsv",
        "systick",
    ]
    vector = {
        "initial_sp": vector_words[0] if vector_words else None,
        "reset_handler": vector_words[1] if len(vector_words) > 1 else None,
        "first_16_words": vector_words,
        "core_vectors": dict(zip(core_vector_names, vector_words, strict=False)),
        "thumb_reset_handler": bool(len(vector_words) > 1 and vector_words[1] & 1),
        "runtime_payload_address": runtime_payload_address,
        "reset_handler_body_offset": reset_handler_body_offset,
        "reset_handler_inside_body": bool(
            reset_handler_body_offset is not None
            and 0 <= reset_handler_body_offset < len(body)
        ),
    }

    strings = ascii_strings(body)
    keywords = (
        "keychron",
        "version",
        "build",
        "boot",
        "dfu",
        "mouse",
        "sensor",
        "battery",
        "pair",
        "poll",
        "report",
        "dpi",
        "rapid",
        "mag",
        "error",
        "fail",
        "assert",
        "crc",
        "nrf",
        "zephyr",
        "usb",
        "hid",
        "paw",
        "ppt",
        "bond",
        "access code",
    )
    selected_strings = [
        entry
        for entry in strings
        if any(keyword in str(entry["text"]).lower() for keyword in keywords)
    ]

    block_size = 4096
    entropy = [
        {
            "body_offset": offset,
            "size": len(body[offset : offset + block_size]),
            "entropy": round(shannon_entropy(body[offset : offset + block_size]), 4),
        }
        for offset in range(0, len(body), block_size)
    ]

    return {
        "path": str(path.resolve()),
        "filename": path.name,
        "file_size": len(data),
        "header": {
            "magic": f"0x{magic:08x}",
            "load_address": f"0x{load_addr:08x}",
            "header_size": hdr_size,
            "protected_tlv_size": protected_tlv_size,
            "image_size": img_size,
            "flags": f"0x{flags:08x}",
            "flag_names": [name for bit, name in FLAG_NAMES.items() if flags & bit],
            "version": f"{ver_major}.{ver_minor}.{ver_revision}+{ver_build}",
            "pad": pad,
        },
        "layout": {
            "body_start": hdr_size,
            "body_end": hdr_size + img_size,
            "tlv_offset": tlv_offset,
            "tlv_total": tlv_total,
            "exact_file_length": tlv_offset + tlv_total == len(data),
        },
        "hashes": hashes,
        "sha512_tlv_matches": sha512_matches,
        "tlv_magic": f"0x{tlv_magic:04x}" if tlv_magic is not None else None,
        "tlvs": tlvs,
        "has_security_counter": any(x["type"] == 0x50 for x in tlvs),
        "has_dependency": any(x["type"] == 0x40 for x in tlvs),
        "is_encrypted": bool(flags & (0x04 | 0x08)),
        "vector_table": vector,
        "string_count": len(strings),
        "selected_strings": selected_strings,
        "entropy_4k": entropy,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("images", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--extract-dir", type=Path)
    args = parser.parse_args()

    reports = [parse_image(path) for path in args.images]
    if args.extract_dir:
        args.extract_dir.mkdir(parents=True, exist_ok=True)
        for report, path in zip(reports, args.images, strict=True):
            data = path.read_bytes()
            start = int(report["header"]["header_size"])
            end = int(report["layout"]["body_end"])
            (args.extract_dir / f"{path.stem}.body.bin").write_bytes(data[start:end])

    output = json.dumps(reports, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return 1 if any(report["errors"] for report in reports) else 0


if __name__ == "__main__":
    raise SystemExit(main())
