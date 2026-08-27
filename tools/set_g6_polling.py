#!/usr/bin/env python3
"""Set and verify the original G6 HE v6 per-mode polling rate."""

from __future__ import annotations

import argparse
import json
import time

import hid

from probe_g6_config_readonly import (
    SHORT_INPUT_REPORT_ID,
    SHORT_OUTPUT_REPORT_ID,
    decode_device,
    decode_polling_separate,
    find_unique_interface,
    short_query,
    strip_report_id,
)


POLLING = [125, 500, 1000, 2000, 4000, 8000]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hz", type=int, choices=POLLING, required=True)
    parser.add_argument("--timeout-ms", type=int, default=2000)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    result: dict[str, object] = {
        "operation": f"set current G6 HE mode to {args.hz} Hz",
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
        device_info = decode_device(short_query(device, 0x02, args.timeout_ms))
        before_raw = short_query(device, 0x4B, args.timeout_ms)
        before = decode_polling_separate(before_raw)
        mode_index = min(int(device_info["work_mode"]), 1)
        levels = [int(item["level"]) for item in before]
        levels[mode_index] = POLLING.index(args.hz)

        payload = bytearray(20)
        payload[0:5] = bytes([0x4A, levels[0], levels[1], 6, 6])
        payload[5:11] = bytes(range(6))
        payload[11:17] = bytes(range(6))
        written = device.write(bytes([SHORT_OUTPUT_REPORT_ID]) + payload)
        response = strip_report_id(
            device.read(21, args.timeout_ms), SHORT_INPUT_REPORT_ID
        )
        time.sleep(0.1)
        after = decode_polling_separate(
            short_query(device, 0x4B, args.timeout_ms)
        )
        result.update(
            {
                "status": "verified"
                if after[mode_index]["level"] == POLLING.index(args.hz)
                else "verification_failed",
                "work_mode": device_info["work_mode"],
                "mode_index": mode_index,
                "bytes_written": written,
                "response_hex": response.hex(),
                "before": before,
                "after": after,
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
