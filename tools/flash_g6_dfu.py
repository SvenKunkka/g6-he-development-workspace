#!/usr/bin/env python3
"""Flash a G6 HE vendor-signed image over its Keychron HID DFU channel.

This follows the Launcher protocol used by the usage-page 0x008C interface:
0x61 version, 0x62 prepare, 0x63 start, 0x64 data, 0x65 CRC, 0x66 switch.
The operation is intentionally destructive and requires --execute.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
import zlib
from pathlib import Path

import hid


VID = 0x3434
PID = 0xD086
USAGE_PAGE = 0x008C
USAGE = 0x0001
INTERFACE = 3
OUTPUT_REPORT_ID = 0xB2
INPUT_REPORT_ID = 0xB1
PACKET_SIZE = 32


def targets() -> list[dict[str, object]]:
    return [
        item
        for item in hid.enumerate(VID, PID)
        if item.get("usage_page") == USAGE_PAGE
        and item.get("usage") == USAGE
        and item.get("interface_number") == INTERFACE
    ]


def frame(payload: bytes) -> bytes:
    return bytes([OUTPUT_REPORT_ID]) + payload.ljust(PACKET_SIZE, b"\x00")


def strip_report_id(report: list[int]) -> bytes:
    raw = bytes(report)
    return raw[1:] if raw and raw[0] == INPUT_REPORT_ID else raw


def control_packet(sequence: int, opcode: int, extra: bytes = b"",
                   ack: bool = False) -> bytes:
    length = 3 + len(extra)
    packet = bytearray(PACKET_SIZE)
    packet[0] = 0xAA
    packet[1] = 0x57 if ack else 0x55
    packet[2] = length
    packet[3] = (~length) & 0xFF
    packet[4] = sequence
    packet[5] = opcode
    packet[6:6 + len(extra)] = extra
    packet[6 + len(extra)] = (opcode + sum(extra)) & 0xFF
    return bytes(packet)


def read_for_opcode(device: hid.device, opcode: int, timeout_ms: int,
                    sequence: int | None = None) -> bytes:
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        remaining = max(1, int((deadline - time.monotonic()) * 1000))
        report = device.read(33, remaining)
        if not report:
            break
        raw = strip_report_id(report)
        if (
            len(raw) >= 9
            and raw[0] == 0xAA
            and raw[7] == opcode
            and (sequence is None or raw[6] == sequence)
        ):
            return raw
    return b""


def status_ok(response: bytes) -> bool:
    return len(response) >= 9 and response[8] == 0


def transact(device: hid.device, packet: bytes, opcode: int, timeout_ms: int,
             sequence: int | None = None, retries: int = 0) -> bytes:
    last = b""
    for attempt in range(retries + 1):
        written = device.write(frame(packet))
        if written != 33:
            raise RuntimeError(f"short HID write: {written}/33")
        last = read_for_opcode(device, opcode, timeout_ms, sequence)
        if last and status_ok(last):
            return last
        if attempt < retries:
            print(
                json.dumps(
                    {
                        "event": "retry",
                        "opcode": f"{opcode:02X}",
                        "sequence": sequence,
                        "attempt": attempt + 2,
                        "response": last.hex(),
                    }
                ),
                flush=True,
            )
    if not last:
        raise TimeoutError(
            f"opcode 0x{opcode:02X} sequence {sequence} acknowledgement timeout"
        )
    raise RuntimeError(
        f"opcode 0x{opcode:02X} sequence {sequence} failed: {last.hex()}"
    )


def data_packet(sequence: int, chunk: bytes, dfu_version: int) -> bytes:
    packet = bytearray(PACKET_SIZE)
    packet[0] = 0xAA
    packet[1] = 0x57
    packet[4] = sequence
    packet[5] = 0x64
    if dfu_version == 1:
        packet[2] = len(chunk) + 3
        packet[6] = 0
        packet[7] = sequence
        offset = 8
    else:
        packet[2] = len(chunk) + 3
        offset = 6
    packet[3] = (~packet[2]) & 0xFF
    packet[offset:offset + len(chunk)] = chunk
    checksum = 0x64 + sum(chunk)
    packet[offset + len(chunk)] = checksum & 0xFF
    packet[offset + len(chunk) + 1] = (checksum >> 8) & 0xFF
    return bytes(packet)


def launcher_crc32(data: bytes) -> int:
    return zlib.crc32(data) ^ 0xFFFFFFFF


def verify_packet(data: bytes) -> bytes:
    crc = launcher_crc32(data)
    crc_le = crc.to_bytes(4, "little")
    body = bytes([0x65]) + crc_le + crc_le
    checksum = sum(body)
    packet = bytearray(PACKET_SIZE)
    packet[0] = 0xAA
    packet[1] = 0x55
    packet[2] = 11
    packet[3] = (~11) & 0xFF
    packet[4] = 1
    packet[5:14] = body
    packet[14] = checksum & 0xFF
    packet[15] = (checksum >> 8) & 0xFF
    return bytes(packet)


def wait_for_target(expected: bool, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if (len(targets()) == 1) == expected:
            return True
        time.sleep(0.1)
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--data-timeout-ms", type=int, default=400)
    args = parser.parse_args()

    image = args.image.resolve()
    data = image.read_bytes()
    matches = targets()
    metadata = {
        "target": f"{VID:04X}:{PID:04X}",
        "matched_update_interfaces": len(matches),
        "image": str(image),
        "image_bytes": len(data),
        "image_sha256": hashlib.sha256(data).hexdigest(),
        "chunks": math.ceil(len(data) / 16),
        "execute": args.execute,
    }
    print(json.dumps({"event": "preflight", **metadata}), flush=True)
    if not args.execute:
        return 2
    if len(matches) != 1:
        raise RuntimeError(f"expected one update interface, found {len(matches)}")

    device = hid.device()
    device.open_path(matches[0]["path"])
    try:
        version_response = transact(
            device, control_packet(2, 0x61), 0x61, 1500
        )
        dfu_version = version_response[10]
        print(
            json.dumps(
                {
                    "event": "dfu_handshake",
                    "dfu_version": dfu_version,
                    "response": version_response.hex(),
                }
            ),
            flush=True,
        )

        prepare = transact(
            device, control_packet(2, 0x62, b"\x00"), 0x62, 5000
        )
        print(
            json.dumps({"event": "prepared", "response": prepare.hex()}),
            flush=True,
        )

        start = transact(
            device,
            control_packet(3, 0x63, bytes([dfu_version]), ack=True),
            0x63,
            5000,
        )
        print(
            json.dumps({"event": "started", "response": start.hex()}),
            flush=True,
        )

        chunks = [data[index:index + 16] for index in range(0, len(data), 16)]
        sequence = 4
        last_percent = -1
        started_at = time.monotonic()
        for index, chunk in enumerate(chunks, start=1):
            transact(
                device,
                data_packet(sequence, chunk, dfu_version),
                0x64,
                args.data_timeout_ms,
                sequence=sequence,
                retries=5,
            )
            percent = index * 100 // len(chunks)
            if percent != last_percent:
                print(
                    json.dumps(
                        {
                            "event": "writing",
                            "percent": percent,
                            "chunk": index,
                            "chunks": len(chunks),
                            "elapsed_seconds": round(
                                time.monotonic() - started_at, 1
                            ),
                        }
                    ),
                    flush=True,
                )
                last_percent = percent
            sequence += 1
            if sequence > 255:
                sequence = 1

        verify = transact(device, verify_packet(data), 0x65, 3000)
        print(
            json.dumps(
                {
                    "event": "verified",
                    "launcher_crc32": f"{launcher_crc32(data):08x}",
                    "response": verify.hex(),
                }
            ),
            flush=True,
        )

        switch = control_packet(1, 0x66)
        written = device.write(frame(switch))
        print(
            json.dumps({"event": "switch_sent", "bytes_written": written}),
            flush=True,
        )
    finally:
        device.close()

    disappeared = wait_for_target(False, 3)
    reappeared = wait_for_target(True, 12)
    print(
        json.dumps(
            {
                "event": "reenumeration",
                "disappeared": disappeared,
                "reappeared": reappeared,
                "matched_update_interfaces": len(targets()),
            }
        ),
        flush=True,
    )
    return 0 if reappeared else 1


if __name__ == "__main__":
    raise SystemExit(main())
