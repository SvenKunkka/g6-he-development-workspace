#!/usr/bin/env python3
"""Enumerate Keychron USB/HID devices without sending feature reports."""

from __future__ import annotations

import argparse
import json
import plistlib
import subprocess

import hid


KEYS = (
    "Product",
    "Manufacturer",
    "VendorID",
    "ProductID",
    "VersionNumber",
    "SerialNumber",
    "PrimaryUsagePage",
    "PrimaryUsage",
    "ReportInterval",
    "MaxInputReportSize",
    "MaxOutputReportSize",
    "MaxFeatureReportSize",
    "BootProtocol",
    "LocationID",
)


def ioreg_entries(class_name: str) -> list[dict[str, object]]:
    raw = subprocess.check_output(["ioreg", "-r", "-c", class_name, "-a"])
    return plistlib.loads(raw)


def walk_ioreg(nodes):
    if isinstance(nodes, dict):
        nodes = [nodes]
    for node in nodes:
        if not isinstance(node, dict):
            continue
        yield node
        children = node.get("IORegistryEntryChildren", [])
        if isinstance(children, list):
            yield from walk_ioreg(children)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    args = parser.parse_args()

    devices = []
    usb_tree = plistlib.loads(
        subprocess.check_output(["ioreg", "-p", "IOUSB", "-l", "-a"])
    )
    for entry in walk_ioreg(usb_tree):
        if entry.get("USB Vendor Name") == "Keychron":
            devices.append(
                {
                    "kind": "usb_device",
                    "product": entry.get("USB Product Name"),
                    "vendor_id": entry.get("idVendor"),
                    "product_id": entry.get("idProduct"),
                    "bcd_device": entry.get("bcdDevice"),
                    "serial": entry.get("USB Serial Number"),
                    "usb_link_speed": entry.get("UsbLinkSpeed"),
                    "location_id": entry.get("locationID"),
                }
            )

    hidapi_interfaces = []
    for entry in hid.enumerate(0x3434, 0):
        hidapi_interfaces.append(
            {
                key: (
                    value.decode(errors="replace")
                    if isinstance((value := entry.get(key)), bytes)
                    else value
                )
                for key in (
                    "path",
                    "vendor_id",
                    "product_id",
                    "serial_number",
                    "release_number",
                    "manufacturer_string",
                    "product_string",
                    "usage_page",
                    "usage",
                    "interface_number",
                )
            }
        )

    interfaces = []
    for entry in ioreg_entries("IOHIDDevice"):
        product = entry.get("Product")
        if entry.get("Manufacturer") == "Keychron" or (
            isinstance(product, str) and product.startswith("Keychron ")
        ):
            interfaces.append({key: entry.get(key) for key in KEYS})

    output = json.dumps(
        {
            "usb_devices": devices,
            "ioreg_hid_interfaces": interfaces,
            "hidapi_interfaces": hidapi_interfaces,
        },
        ensure_ascii=False,
        indent=2,
    )
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(output + "\n")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
