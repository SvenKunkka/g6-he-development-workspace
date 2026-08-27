#!/usr/bin/env python3
"""Restore only the original G6 HE DPI table to official safe defaults.

This sends the v6 separate-X/Y command 0x48 advertised by the live device
feature flags. It does not reset, erase, update firmware, or enter a bootloader.
"""

from __future__ import annotations

import argparse
import json
import time

import hid

from probe_g6_config_readonly import (
    INTERFACE,
    LONG_OUTPUT_REPORT_ID,
    PID,
    SHORT_INPUT_REPORT_ID,
    USAGE,
    USAGE_PAGE,
    VID,
    decode_dpi_xy,
    find_unique_interface,
    long_query,
    strip_report_id,
)


DEFAULT_DPI = [400, 800, 1600, 3200, 5000]
ACTIVE_LEVEL = 2
LEVEL_COUNT = len(DEFAULT_DPI)


def build_command() -> bytes:
    payload = bytearray(63)
    payload[0] = 0x48
    payload[1:4] = bytes([ACTIVE_LEVEL] * 3)
    payload[4] = LEVEL_COUNT
    for index, value in enumerate(DEFAULT_DPI):
        payload[5 + index * 2] = value & 0xFF
        payload[6 + index * 2] = value >> 8
        payload[21 + index * 2] = value & 0xFF
        payload[22 + index * 2] = value >> 8
    payload[37] = 0
    return bytes(payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout-ms", type=int, default=1500)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="required guard; without it the tool only prints the exact packet",
    )
    args = parser.parse_args()

    payload = build_command()
    result: dict[str, object] = {
        "target": f"{VID:04X}:{PID:04X} usage {USAGE_PAGE:04X}:{USAGE:04X} interface {INTERFACE}",
        "operation": "restore official DPI defaults only",
        "defaults": DEFAULT_DPI,
        "active_level": ACTIVE_LEVEL,
        "level_count": LEVEL_COUNT,
        "raw_hid_write_hex": (bytes([LONG_OUTPUT_REPORT_ID]) + payload).hex(),
        "firmware_update": False,
        "reset_or_erase": False,
        "executed": args.execute,
    }
    if not args.execute:
        result["status"] = "dry_run"
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    device = hid.device()
    started = time.monotonic()
    try:
        match = find_unique_interface()
        device.open_path(match["path"])
        before = long_query(device, 0x49, args.timeout_ms)
        written = device.write(bytes([LONG_OUTPUT_REPORT_ID]) + payload)
        response = strip_report_id(
            device.read(64, args.timeout_ms), SHORT_INPUT_REPORT_ID
        )
        after = long_query(device, 0x49, args.timeout_ms)
        result.update(
            {
                "status": "verified"
                if decode_dpi_xy(after)["values_x"] == DEFAULT_DPI
                and decode_dpi_xy(after)["values_y"] == DEFAULT_DPI
                and decode_dpi_xy(after)["level_count"] == LEVEL_COUNT
                else "verification_failed",
                "bytes_written": written,
                "response_hex": response.hex(),
                "before": decode_dpi_xy(before),
                "after": decode_dpi_xy(after),
                "elapsed_ms": round((time.monotonic() - started) * 1000, 1),
            }
        )
    except Exception as exc:
        result.update(
            {
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
                "elapsed_ms": round((time.monotonic() - started) * 1000, 1),
            }
        )
    finally:
        device.close()

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
