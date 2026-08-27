#!/usr/bin/env python3
"""Capture ordinary G6 HE mouse input reports without sending any command."""

from __future__ import annotations

import argparse
import json
import time

import hid


VID = 0x3434
PID = 0xD086
USAGE_PAGE = 0x0001
USAGE = 0x0002
INTERFACE = 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=10.0)
    args = parser.parse_args()

    matches = [
        item
        for item in hid.enumerate(VID, PID)
        if item.get("usage_page") == USAGE_PAGE
        and item.get("usage") == USAGE
        and item.get("interface_number") == INTERFACE
    ]
    result: dict[str, object] = {
        "target": f"{VID:04X}:{PID:04X} mouse interface {INTERFACE}",
        "matched_interfaces": len(matches),
        "duration_seconds": args.seconds,
        "commands_sent": False,
        "reports": [],
    }
    if len(matches) != 1:
        result["status"] = "target_not_unique"
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2

    device = hid.device()
    started = time.monotonic()
    reports: list[str] = []
    try:
        device.open_path(matches[0]["path"])
        while time.monotonic() - started < args.seconds:
            report = device.read(8, 100)
            if report:
                reports.append(bytes(report).hex())
                if len(reports) >= 100:
                    break
        result["reports"] = reports
        result["report_count"] = len(reports)
        result["status"] = "input_active" if reports else "no_input_reports"
    except Exception as exc:
        result["status"] = "error"
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        device.close()

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if reports else 1


if __name__ == "__main__":
    raise SystemExit(main())
