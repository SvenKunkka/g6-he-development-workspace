#!/usr/bin/env python3
"""Bounded, read-only G6 HE Launcher protocol probe.

Only two whitelisted query opcodes are sent:
  report 0x51, opcode 7: current base configuration
  report 0x51, opcode 6: firmware/device information

No configuration, pairing, DFU, reset, or output-control command is permitted.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import time
from pathlib import Path
from queue import Empty
from typing import Any

import hid


VID = 0x3434
PID = 0xD086
USAGE_PAGE = 0xFFC1
USAGE = 1
REPORT_ID = 0x51
ALLOWED_QUERY_OPCODES = (7, 6)
FEATURE_READ_LENGTHS = (65, 64, 21)


def find_exact_interface() -> bytes:
    candidates = [
        item
        for item in hid.enumerate(VID, PID)
        if int(item.get("usage_page") or -1) == USAGE_PAGE
        and int(item.get("usage") or -1) == USAGE
    ]
    if len(candidates) != 1:
        raise RuntimeError(
            f"expected exactly one G6 HE config interface, found {len(candidates)}"
        )
    path = candidates[0].get("path")
    if not isinstance(path, bytes):
        raise RuntimeError("HID interface path is unavailable")
    return path


def worker(path: bytes, queue: mp.Queue[Any]) -> None:
    device = hid.device()
    stage = "open"
    partial: dict[str, Any] = {}
    try:
        device.open_path(path)
        responses: dict[str, Any] = {}
        for opcode in ALLOWED_QUERY_OPCODES:
            stage = f"send opcode {opcode}"
            payload = bytearray(21)
            payload[0] = REPORT_ID
            payload[1] = opcode
            sent = device.send_feature_report(bytes(payload))
            partial[str(opcode)] = {"sent_bytes": sent}
            read_errors: list[str] = []
            response = b""
            for read_length in FEATURE_READ_LENGTHS:
                stage = f"receive opcode {opcode} length {read_length}"
                try:
                    response = bytes(
                        device.get_feature_report(REPORT_ID, read_length)
                    )
                    break
                except OSError as exc:
                    read_errors.append(f"{read_length}: {exc}")
            if not response:
                raise OSError(
                    "all feature-report lengths failed: " + "; ".join(read_errors)
                )
            responses[str(opcode)] = {
                "sent_bytes": sent,
                "response_hex": response.hex(),
                "response_length": len(response),
                "attempted_read_lengths": list(FEATURE_READ_LENGTHS),
            }
        queue.put({"ok": True, "responses": responses})
    except Exception as exc:  # hidapi exposes platform-specific exception classes.
        queue.put(
            {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "failure_stage": stage,
                "partial": partial,
            }
        )
    finally:
        try:
            device.close()
        except Exception:
            pass


def probe(timeout_seconds: float) -> dict[str, Any]:
    started = time.monotonic()
    try:
        path = find_exact_interface()
    except Exception as exc:
        return {
            "ok": False,
            "timed_out": False,
            "error": f"{type(exc).__name__}: {exc}",
        }

    queue: mp.Queue[Any] = mp.Queue()
    process = mp.Process(target=worker, args=(path, queue), daemon=True)
    process.start()
    process.join(timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join(1)
        result: dict[str, Any] = {
            "ok": False,
            "timed_out": True,
            "error": f"read-only HID probe exceeded {timeout_seconds:.1f}s",
        }
    else:
        try:
            result = queue.get_nowait()
        except Empty:
            result = {
                "ok": False,
                "timed_out": False,
                "error": f"probe exited with code {process.exitcode} without a result",
            }
        result["timed_out"] = False

    result.update(
        {
            "vendor_id": f"0x{VID:04X}",
            "product_id": f"0x{PID:04X}",
            "usage_page": f"0x{USAGE_PAGE:04X}",
            "report_id": f"0x{REPORT_ID:02X}",
            "query_opcodes": list(ALLOWED_QUERY_OPCODES),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "mutating_commands_sent": False,
        }
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = probe(args.timeout)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
