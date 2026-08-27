#!/usr/bin/env python3
"""Reset a uniquely connected G6 HE through its verified update command.

Opcode 0x66 is statically confirmed to send an acknowledgement and schedule
the firmware's AIRCR SYSRESETREQ handler. It does not erase or write firmware.
"""

from __future__ import annotations

import json
import time

import hid


VID = 0x3434
PID = 0xD086
USAGE_PAGE = 0x008C
USAGE = 0x0001
INTERFACE = 3
OUTPUT_REPORT_ID = 0xB2


def targets() -> list[dict[str, object]]:
    return [
        item
        for item in hid.enumerate(VID, PID)
        if item.get("usage_page") == USAGE_PAGE
        and item.get("usage") == USAGE
        and item.get("interface_number") == INTERFACE
    ]


def main() -> int:
    matches = targets()
    result: dict[str, object] = {
        "target": f"{VID:04X}:{PID:04X}",
        "usage_page": f"{USAGE_PAGE:04X}",
        "interface": INTERFACE,
        "matched_interfaces_before": len(matches),
        "command": "VERIFIED_SYSTEM_RESET_0x66",
        "flash_write": False,
        "flash_erase": False,
    }
    if len(matches) != 1:
        result["status"] = "target_not_unique"
        print(json.dumps(result, indent=2))
        return 2

    packet = bytearray(32)
    packet[:7] = bytes([0xAA, 0x55, 0x03, 0xFC, 0x01, 0x66, 0x66])
    device = hid.device()
    try:
        device.open_path(matches[0]["path"])
        result["bytes_written"] = device.write(
            bytes([OUTPUT_REPORT_ID]) + bytes(packet)
        )
        try:
            response = device.read(33, 500)
            result["ack_hex"] = bytes(response).hex()
        except Exception as exc:
            result["ack_error"] = f"{type(exc).__name__}: {exc}"
    finally:
        device.close()

    observations: list[dict[str, object]] = []
    started = time.monotonic()
    while time.monotonic() - started < 8:
        count = len(targets())
        observations.append(
            {
                "elapsed_ms": round((time.monotonic() - started) * 1000),
                "matched_interfaces": count,
            }
        )
        if count == 1 and time.monotonic() - started > 0.5:
            break
        time.sleep(0.1)

    result["reenumeration"] = observations
    result["matched_interfaces_after"] = len(targets())
    result["status"] = (
        "reenumerated" if result["matched_interfaces_after"] == 1 else "missing"
    )
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "reenumerated" else 1


if __name__ == "__main__":
    raise SystemExit(main())
