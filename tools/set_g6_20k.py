#!/usr/bin/env python3
"""Enable the original G6 HE 20K/max-speed sensor mode and verify readback."""

from __future__ import annotations

import argparse
import json
import time

import hid

from probe_g6_config_readonly import (
    SHORT_INPUT_REPORT_ID,
    SHORT_OUTPUT_REPORT_ID,
    decode_base,
    find_unique_interface,
    long_query,
    strip_report_id,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout-ms", type=int, default=2000)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    payload = bytearray(20)
    payload[0] = 0x42
    payload[1] = 1
    payload[2:5] = bytes([2, 2, 2])
    payload[6] = 1
    payload[8] = 2
    result: dict[str, object] = {
        "operation": "enable original G6 HE 20K/max-speed sensor mode",
        "raw_hid_write_hex": (
            bytes([SHORT_OUTPUT_REPORT_ID]) + payload
        ).hex(),
        "firmware_update": False,
        "flash_erase": False,
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
        before = long_query(device, 0x06, args.timeout_ms)
        written = device.write(bytes([SHORT_OUTPUT_REPORT_ID]) + payload)
        response = strip_report_id(
            device.read(21, args.timeout_ms), SHORT_INPUT_REPORT_ID
        )
        time.sleep(0.25)
        after = long_query(device, 0x06, args.timeout_ms)
        result.update(
            {
                "status": "verified"
                if decode_base(after)["fps20k"]
                else "verification_failed",
                "bytes_written": written,
                "response_hex": response.hex(),
                "before": decode_base(before),
                "after": decode_base(after),
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
