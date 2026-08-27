#!/usr/bin/env python3
"""Read-only probe for the original G6 HE configuration HID interface.

The interface is a numbered-output/input HID channel:

* report B3: 63-byte long command payload
* report B4: 63-byte long response payload
* report B5: 20-byte short command payload
* report B6: 20-byte short response payload

Only documented read commands are transmitted, including the v6 separate-DPI
and separate-polling queries advertised by the device feature flags.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import hid


VID = 0x3434
PID = 0xD086
USAGE_PAGE = 0xFFC1
USAGE = 0x0001
INTERFACE = 2
LONG_OUTPUT_REPORT_ID = 0xB3
LONG_INPUT_REPORT_ID = 0xB4
SHORT_OUTPUT_REPORT_ID = 0xB5
SHORT_INPUT_REPORT_ID = 0xB6


def find_unique_interface() -> dict[str, object]:
    matches = [
        item
        for item in hid.enumerate(VID, PID)
        if item.get("usage_page") == USAGE_PAGE
        and item.get("usage") == USAGE
        and item.get("interface_number") == INTERFACE
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"expected one G6 HE config interface, found {len(matches)}"
        )
    return matches[0]


def strip_report_id(report: list[int], expected: int) -> bytes:
    raw = bytes(report)
    return raw[1:] if raw and raw[0] == expected else raw


def long_query(device: hid.device, command: int, timeout_ms: int) -> bytes:
    payload = bytearray(63)
    payload[0] = command
    written = device.write(bytes([LONG_OUTPUT_REPORT_ID]) + payload)
    if written != 64:
        raise RuntimeError(f"long write returned {written}, expected 64")
    response = strip_report_id(
        device.read(64, timeout_ms), LONG_INPUT_REPORT_ID
    )
    if not response:
        raise TimeoutError(f"command 0x{command:02X} timed out")
    if response[0] != command:
        raise RuntimeError(
            f"command 0x{command:02X} got response 0x{response[0]:02X}"
        )
    return response


def short_query(device: hid.device, command: int, timeout_ms: int) -> bytes:
    payload = bytearray(20)
    payload[0] = command
    written = device.write(bytes([SHORT_OUTPUT_REPORT_ID]) + payload)
    if written != 21:
        raise RuntimeError(f"short write returned {written}, expected 21")
    response = strip_report_id(
        device.read(21, timeout_ms), SHORT_INPUT_REPORT_ID
    )
    if not response:
        raise TimeoutError(f"command 0x{command:02X} timed out")
    if response[0] != command:
        raise RuntimeError(
            f"command 0x{command:02X} got response 0x{response[0]:02X}"
        )
    return response


def u16le(data: bytes, offset: int) -> int:
    return data[offset] | data[offset + 1] << 8


def decode_base(data: bytes) -> dict[str, object]:
    return {
        "profile": data[1],
        "dpi_level_by_mode": [data[2] & 0x0F, data[3] & 0x0F, data[4] & 0x0F],
        "dpi_values": [u16le(data, 5 + 2 * index) for index in range(5)],
        "system_flags": data[15],
        "dpi_level_count": data[16],
        "debounce_ms": data[17],
        "sleep_time": data[18],
        "polling_level_by_mode": [
            data[2] >> 4,
            data[3] >> 4,
            data[4] >> 4,
        ],
        "dpi_max": u16le(data, 40),
        "dpi_step": data[42] or 50,
        "polling_table": list(data[43:49]),
        "polling_level_count": data[49] or 6,
        "fps20k": bool(data[52] & 1),
        "angle": data[55] - 256 if data[55] > 90 else data[55],
        "feature_flags": {
            "feature1": data[26],
            "feature2": data[53],
            "feature3": data[60],
        },
    }


def decode_version(data: bytes) -> str:
    length = min(data[1], len(data) - 2)
    return data[2 : 2 + length].decode("ascii", errors="replace")


def decode_device(data: bytes) -> dict[str, object]:
    return {
        "protocol_version": u16le(data, 1),
        "vid": f"{u16le(data, 3):04X}",
        "pid": f"{u16le(data, 5):04X}",
        "firmware_version": (
            f"{data[8]}.{(data[7] >> 4) & 0x0F}.{data[7] & 0x0F}"
        ),
        "work_mode": data[9] & 0x07,
        "feature_flags": {
            "feature1": data[11],
            "feature2": data[12],
            "feature3": data[13],
            "feature4": data[15],
        },
    }


def decode_he(data: bytes) -> list[dict[str, object]]:
    sections: list[dict[str, object]] = []
    section_length = 22
    for index in range(min(data[1], 2)):
        offset = section_length * index
        adc_flag = data[19 + offset]
        section: dict[str, object] = {
            "index": data[2 + offset],
            "dead_band": [data[3 + offset], data[4 + offset]],
            "percent_point": [data[5 + offset], data[6 + offset]],
            "scale_point": [
                u16le(data, 7 + offset),
                u16le(data, 9 + offset),
            ],
            "percent_value": data[11 + offset],
            "scale_value": u16le(data, 12 + offset),
            "trigger_mode": data[14 + offset] & 0x0F,
            "rapid_trigger_enabled": data[14 + offset] >> 4,
            "rapid_trigger_value": [
                u16le(data, 15 + offset),
                u16le(data, 17 + offset),
            ],
            "adc_flag": adc_flag,
        }
        if adc_flag == 1 and 23 + offset < len(data):
            section["adc"] = [
                u16le(data, 20 + offset),
                u16le(data, 22 + offset),
            ]
        elif adc_flag == 2:
            section["ir_trigger"] = data[20 + offset]
        sections.append(section)
    return sections


def decode_dpi_xy(data: bytes) -> dict[str, object]:
    return {
        "level_x_by_mode": [data[index] & 0x0F for index in range(1, 4)],
        "level_y_by_mode": [data[index] >> 4 for index in range(1, 4)],
        "level_count": data[4],
        "values_x": [u16le(data, 5 + 2 * index) for index in range(5)],
        "values_y": [u16le(data, 21 + 2 * index) for index in range(5)],
        "enabled": [
            (data[37] >> index) & 1 for index in range(8)
        ],
    }


def decode_polling_separate(data: bytes) -> list[dict[str, object]]:
    return [
        {
            "level": data[1],
            "level_count": data[3],
            "table": list(data[5:11]),
        },
        {
            "level": data[2],
            "level_count": data[4],
            "table": list(data[11:17]),
        },
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout-ms", type=int, default=1500)
    parser.add_argument("--output")
    args = parser.parse_args()

    result: dict[str, object] = {
        "target": {
            "vid": f"{VID:04X}",
            "pid": f"{PID:04X}",
            "usage_page": f"{USAGE_PAGE:04X}",
            "usage": USAGE,
            "interface": INTERFACE,
            "long_reports": "B3 output / B4 input",
            "short_reports": "B5 output / B6 input",
        },
        "commands": [
            "GET_DEVICE_0x02",
            "GET_VERSION_0x04",
            "GET_BASE_0x06",
            "GET_DPI_XY_0x49",
            "GET_POLLING_SEPARATE_0x4B",
            "GET_HE_0x65",
        ],
        "mutating_commands_sent": False,
    }

    device = hid.device()
    started = time.monotonic()
    try:
        match = find_unique_interface()
        device.open_path(match["path"])
        raw_device = short_query(device, 0x02, args.timeout_ms)
        raw_version = long_query(device, 0x04, args.timeout_ms)
        raw_base = long_query(device, 0x06, args.timeout_ms)
        raw_dpi_xy = long_query(device, 0x49, args.timeout_ms)
        raw_polling = short_query(device, 0x4B, args.timeout_ms)
        raw_he = long_query(device, 0x65, args.timeout_ms)
        result.update(
            {
                "status": "response",
                "elapsed_ms": round((time.monotonic() - started) * 1000, 1),
                "raw": {
                    "device_b6": raw_device.hex(),
                    "version_b4": raw_version.hex(),
                    "base_b4": raw_base.hex(),
                    "dpi_xy_b4": raw_dpi_xy.hex(),
                    "polling_separate_b6": raw_polling.hex(),
                    "he_b4": raw_he.hex(),
                },
                "decoded": {
                    "device": decode_device(raw_device),
                    "version": decode_version(raw_version),
                    "base": decode_base(raw_base),
                    "dpi_xy": decode_dpi_xy(raw_dpi_xy),
                    "polling_separate": decode_polling_separate(raw_polling),
                    "he": decode_he(raw_he),
                },
            }
        )
    except Exception as exc:
        result.update(
            {
                "status": "error",
                "elapsed_ms": round((time.monotonic() - started) * 1000, 1),
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
    finally:
        device.close()

    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if result["status"] == "response" else 1


if __name__ == "__main__":
    raise SystemExit(main())
