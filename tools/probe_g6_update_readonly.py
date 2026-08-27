#!/usr/bin/env python3
"""Read-only probe for the G6 HE 0x008C HID update interface.

The only transmitted command is opcode 0x60, which the original firmware
dispatch table and Keychron Launcher both identify as a version/info query.
No update-init, data-write, verify, switch, reset, or bootloader opcode is sent.
"""

from __future__ import annotations

import argparse
import json
import time

import hid


VID = 0x3434
PID = 0xD086
USAGE_PAGE = 0x008C
USAGE = 0x0001
INTERFACE = 3
OUTPUT_REPORT_ID = 0xB2
INPUT_REPORT_ID = 0xB1
PACKET_SIZE = 32


def build_info_query(sequence: int = 1) -> bytes:
    packet = bytearray(PACKET_SIZE)
    packet[0] = 0xAA
    packet[1] = 0x55
    packet[2] = 0x03
    packet[3] = 0xFC
    packet[4] = sequence
    packet[5] = 0x60
    packet[6] = 0x60
    return bytes(packet)


def strip_report_id(report: list[int]) -> bytes:
    raw = bytes(report)
    if raw and raw[0] == INPUT_REPORT_ID:
        return raw[1:]
    return raw


def decode_info_frames(frames: list[bytes]) -> dict[str, object]:
    if not frames or len(frames[0]) < 5:
        return {}

    first = frames[0]
    if first[:2] != b"\xAA\x55":
        return {"decode_error": "unexpected response header"}

    payload_length = first[2]
    payload = bytearray(first[5:])
    for frame in frames[1:]:
        payload.extend(frame)
    payload = payload[:payload_length]

    def ascii_field(start: int, end: int) -> str:
        return bytes(value for value in payload[start:end] if value).decode(
            "ascii", errors="replace"
        )

    decoded: dict[str, object] = {
        "declared_payload_length": payload_length,
        "assembled_payload_hex": bytes(payload).hex(),
    }
    if len(payload) >= 36 and payload[0] == 0xA3 and payload[2] == 0x60:
        decoded.update(
            {
                "response_type": f"{payload[0]:02X}",
                "sequence": payload[1],
                "opcode": f"{payload[2]:02X}",
                "status": payload[3],
                "module_model": ascii_field(4, 14),
                "module_version": ascii_field(4, 14),
                "firmware_version": ascii_field(16, 26),
                "hardware_version": ascii_field(26, 36),
            }
        )
    return decoded


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout-ms", type=int, default=1500)
    parser.add_argument("--output")
    args = parser.parse_args()

    matches = [
        item
        for item in hid.enumerate(VID, PID)
        if item.get("usage_page") == USAGE_PAGE
        and item.get("usage") == USAGE
        and item.get("interface_number") == INTERFACE
    ]

    result: dict[str, object] = {
        "target": {
            "vid": f"{VID:04X}",
            "pid": f"{PID:04X}",
            "usage_page": f"{USAGE_PAGE:04X}",
            "usage": USAGE,
            "interface": INTERFACE,
            "output_report_id": f"{OUTPUT_REPORT_ID:02X}",
            "input_report_id": f"{INPUT_REPORT_ID:02X}",
        },
        "matched_interfaces": len(matches),
        "command": "GET_MODULE_INFO_0x60",
        "mutating_commands_sent": False,
        "query_hex": build_info_query().hex(),
    }

    if len(matches) != 1:
        result["status"] = "target_not_unique"
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2

    device = hid.device()
    started = time.monotonic()
    try:
        device.open_path(matches[0]["path"])
        query = bytes([OUTPUT_REPORT_ID]) + build_info_query()
        written = device.write(query)
        first_report = device.read(33, args.timeout_ms)
        frames: list[bytes] = []
        if first_report:
            frames.append(strip_report_id(first_report))
            declared_payload_length = (
                frames[0][2]
                if len(frames[0]) >= 3 and frames[0][:2] == b"\xAA\x55"
                else 0
            )
            assembled_payload_length = max(0, len(frames[0]) - 5)
            while (
                declared_payload_length > assembled_payload_length
                and len(frames) < 8
            ):
                continuation = device.read(33, args.timeout_ms)
                if not continuation:
                    break
                continuation_frame = strip_report_id(continuation)
                frames.append(continuation_frame)
                assembled_payload_length += len(continuation_frame)
        result["bytes_written"] = written
        result["elapsed_ms"] = round((time.monotonic() - started) * 1000, 1)
        result["response_frames_hex"] = [frame.hex() for frame in frames]
        result["response_frame_count"] = len(frames)
        result["decoded"] = decode_info_frames(frames)
        result["status"] = "response" if frames else "timeout"
    except Exception as exc:
        result["elapsed_ms"] = round((time.monotonic() - started) * 1000, 1)
        result["status"] = "error"
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        device.close()

    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(rendered + "\n")
    return 0 if result["status"] == "response" else 1


if __name__ == "__main__":
    raise SystemExit(main())
