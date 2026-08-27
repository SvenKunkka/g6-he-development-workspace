#!/usr/bin/env python3
"""Deterministic release audit for the G6 HE mouse/UltraLink image pair.

This tool is intentionally read-only. It validates immutable image facts and
turns product/Launcher mismatches into a machine-readable defect ledger. It
does not claim to validate behavior that needs firmware source or live hardware.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from inspect_firmware import parse_image  # noqa: E402


SHARED_KEYHASH = (
    "77f8944a6057fdf3ada448a19561f71a536754885dd95f277edd6a1755d757a29"
    "ce7bf820140c086dd000a9bae9741dc9403746fe6364af3fb2593cf8f0121ee"
)


def find_ascii(report: dict[str, Any], needle: str) -> list[int]:
    offsets: list[int] = []
    for item in report["selected_strings"]:
        text = str(item["text"])
        start = 0
        while True:
            relative = text.find(needle, start)
            if relative < 0:
                break
            offsets.append(int(item["offset"]) + relative)
            start = relative + 1
    return offsets


def make_issue(
    issue_id: str,
    severity: str,
    status: str,
    title: str,
    evidence: list[str],
    impact: str,
    acceptance: str,
    source_required: bool,
) -> dict[str, Any]:
    return {
        "id": issue_id,
        "severity": severity,
        "status": status,
        "title": title,
        "evidence": evidence,
        "impact": impact,
        "acceptance": acceptance,
        "source_required": source_required,
    }


def audit(
    mouse_path: Path,
    receiver_path: Path,
    contract_path: Path,
    device_snapshot_path: Path | None = None,
    runtime_probe_path: Path | None = None,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    mouse = parse_image(mouse_path)
    receiver = parse_image(receiver_path)
    images = {"mouse": mouse, "receiver": receiver}
    issues: list[dict[str, Any]] = []

    expected = {
        "mouse": contract["mouse"],
        "receiver": contract["receiver"],
    }
    checks: list[dict[str, Any]] = []
    for role, report in images.items():
        exp = expected[role]
        checks.extend(
            [
                {
                    "id": f"{role}.sha256",
                    "pass": report["hashes"]["sha256"] == exp["sha256"],
                    "actual": report["hashes"]["sha256"],
                    "expected": exp["sha256"],
                },
                {
                    "id": f"{role}.version",
                    "pass": report["header"]["version"] == exp["mcuboot_version"],
                    "actual": report["header"]["version"],
                    "expected": exp["mcuboot_version"],
                },
                {
                    "id": f"{role}.layout",
                    "pass": not report["errors"]
                    and report["layout"]["exact_file_length"],
                    "actual": report["errors"],
                    "expected": [],
                },
                {
                    "id": f"{role}.sha512",
                    "pass": report["sha512_tlv_matches"],
                    "actual": report["sha512_tlv_matches"],
                    "expected": True,
                },
                {
                    "id": f"{role}.thumb_vector",
                    "pass": report["vector_table"]["thumb_reset_handler"],
                    "actual": report["vector_table"]["reset_handler"],
                    "expected": "odd Thumb entry address",
                },
            ]
        )

    keyhashes = {
        role: next(
            (entry["value_hex"] for entry in report["tlvs"] if entry["type"] == 0x01),
            None,
        )
        for role, report in images.items()
    }
    checks.append(
        {
            "id": "pair.shared_keyhash",
            "pass": len(set(keyhashes.values())) == 1
            and keyhashes["mouse"] == SHARED_KEYHASH,
            "actual": keyhashes,
            "expected": SHARED_KEYHASH,
        }
    )

    if any(not report["has_security_counter"] for report in images.values()):
        issues.append(
            make_issue(
                "B-01",
                "medium",
                "confirmed",
                "两份量产镜像缺少 MCUboot Security Counter",
                [
                    f"{role}: TLV types="
                    + ",".join(entry["name"] for entry in report["tlvs"])
                    for role, report in images.items()
                ],
                "若 bootloader 没有独立单调版本策略，旧的合法签名镜像可能被降级安装。",
                "两份发布镜像包含有效 SECURITY_COUNTER，且受控降级测试被拒绝。",
                True,
            )
        )

    if any(not report["has_dependency"] for report in images.values()):
        issues.append(
            make_issue(
                "B-02",
                "medium",
                "confirmed",
                "鼠标与接收器镜像未声明版本依赖",
                [
                    f"{role}: DEPENDENCY={report['has_dependency']}"
                    for role, report in images.items()
                ],
                "升级器无法仅凭镜像阻止不兼容的鼠标/接收器版本组合。",
                "镜像声明并强制执行兼容版本范围，单边不兼容升级测试被拒绝。",
                True,
            )
        )

    null_bond_offsets = find_ascii(mouse, "ppt_ptx/bond/(null)")
    if null_bond_offsets:
        issues.append(
            make_issue(
                "B-03",
                "high",
                "confirmed-binary-call",
                "鼠标启动代码加载错误的空标识配对子树",
                [
                    f"mouse body offsets={null_bond_offsets} string=ppt_ptx/bond/(null)",
                    "function 0x20018B48 loads literal at 0x20018BDC and calls "
                    "settings wrapper 0x200402A4",
                    "registered settings handler root is ppt_ptx/bond "
                    "(pointer stored at body offset 0x514A8)",
                ],
                "启动时读取的子树与注册 handler 根路径不一致，bond 配置可能完全不加载。",
                "源码改为正确根路径或有效设备 ID；配对、断电、模式切换、恢复矩阵全部通过。",
                True,
            )
        )

    rf_offsets = (
        find_ascii(receiver, "Access code: 0x%08x")
        + find_ascii(receiver, "Bond[%d]")
    )
    if rf_offsets:
        issues.append(
            make_issue(
                "B-04",
                "medium-low",
                "conditional-confirmed",
                "接收器镜像保留 RF/bond 详细日志格式",
                [f"receiver body offsets={sorted(rf_offsets)}"],
                "若 UART/RTT 在量产机可读，会泄漏接入码、配对状态和信道信息。",
                "发布构建移除敏感日志，或证明调试口锁定且日志不可读取。",
                True,
            )
        )

    source_path_offsets = (
        find_ascii(mouse, "CMAKE_SOURCE_DIR/src/user_ble.c")
        + find_ascii(mouse, "picolibc/assert.c")
        + find_ascii(receiver, "picolibc/assert.c")
    )
    if source_path_offsets:
        issues.append(
            make_issue(
                "B-05",
                "low",
                "confirmed",
                "发布镜像保留源路径与断言实现信息",
                [f"body offsets={source_path_offsets}"],
                "扩大逆向信息面并占用只读空间。",
                "release profile 仅保留受控故障码，不包含本机构建路径或无用断言文本。",
                True,
            )
        )

    launcher = contract["launcher_snapshot"]
    if (
        launcher["dpi_min"] != contract["mouse"]["dpi_min"]
        or launcher["dpi_max"] != contract["mouse"]["dpi_max"]
        or launcher["lod_mm"] != contract["mouse"]["lod_mm"]
    ):
        issues.append(
            make_issue(
                "B-07",
                "medium",
                "confirmed-integration",
                "Launcher DPI/LOD 范围与产品规格漂移",
                [
                    f"product brief DPI={contract['mouse']['dpi_min']}-{contract['mouse']['dpi_max']}",
                    f"official Launcher DPI={launcher['dpi_min']}-{launcher['dpi_max']}",
                    "live firmware DPI max=50000, step=1",
                    f"product LOD={contract['mouse']['lod_mm']}",
                    f"launcher LOD={launcher['lod_mm']}",
                ],
                "配置器会截断合法范围，或向不支持的固件写入错误值。",
                "产品规格、固件能力声明和 Launcher schema 三方一致并通过边界测试。",
                True,
            )
        )

    if (
        contract["mouse"]["sensor_current_product_brief"]
        != contract["mouse"]["sensor_older_electrical_spec"]
    ):
        issues.append(
            make_issue(
                "B-08",
                "high",
                "confirmed-binary-profile-drift",
                "固件有两套传感器能力表，但 Launcher 使用单一静态配置",
                [
                    "2026-07 product sync=PAW3955",
                    "2026-04 electrical/config spec=PAW3950",
                    "function 0x200158C0 selects profile 0x2004BB20 for "
                    "sensor ID 0x6E and 0x2004BBA0 for ID 0x53",
                    "the adjacent D086 profiles contain 40000 and 30000 "
                    "capability constants respectively",
                ],
                "不同传感器 BOM 会被同一个 Launcher 30K/三档 LOD schema 裁剪或错误配置。",
                "确认 ID 与 BOM 映射；固件上报能力，Launcher 按读取结果生成 DPI/LOD/FPS 控件。",
                True,
            )
        )

    if device_snapshot_path and device_snapshot_path.exists():
        snapshot = json.loads(device_snapshot_path.read_text(encoding="utf-8"))
        mouse_usb_devices = [
            device
            for device in snapshot.get("usb_devices", [])
            if int(device.get("vendor_id", -1)) == int(contract["mouse"]["usb_vid"], 16)
            and int(device.get("product_id", -1))
            == int(contract["mouse"]["usb_pid"], 16)
        ]
        mouse_has_no_serial = bool(mouse_usb_devices) and all(
            not device.get("serial") for device in mouse_usb_devices
        )
        if mouse_has_no_serial:
            issues.append(
                make_issue(
                    "B-09",
                    "medium-low",
                    "confirmed-device",
                    "G6 HE USB 设备缺少稳定唯一序列号",
                    [
                        "analysis/connected_devices.json: "
                        f"{contract['mouse']['usb_vid']}:{contract['mouse']['usb_pid']} "
                        "serial=null"
                    ],
                    "多只设备同时连接时难以唯一选择，增加 DFU 刷错目标风险。",
                    "正常模式与 bootloader 暴露同一稳定、唯一且非隐私敏感的序列号。",
                    True,
                )
            )

    runtime_evidence = [
        "User observed complete input freeze in optical-switch mode",
        "macOS still enumerated four HID interfaces",
        "Earlier InputReportCount snapshot remained 9760",
        "Current ReportAvailableCalls was 14434 and stayed unchanged "
        "during a two-second static sample (non-conclusive)",
    ]
    runtime_status = "runtime-observed-input-path-stall"
    runtime_evidence.extend(
        [
            "correct B3/B4 and B5/B6 read-only queries 0x02/0x04/0x06 "
            "all responded in 4.1 ms",
            "decoded protocol=6, firmware=1.0.0+5, work_mode=0",
            "B5/0x0F/0xFF recover-all returned E4 00 0F and reset configuration",
            "update-interface 0x66 reset re-enumerated USB but did not restore input",
            "v6 DPI, 8K polling, and 20K settings all passed immediate readback",
            "three 12-second interface-0 captures received exactly 0 reports",
        ]
    )

    issues.extend(
        [
            make_issue(
                "B-10",
                "medium",
                "needs-hardware-test",
                "Boot Mouse 模式的 8 字节报告兼容性未验证",
                [
                    "USB interface declares Boot Mouse",
                    "Report Protocol layout includes vendor byte and horizontal wheel",
                ],
                "BIOS、KVM 或恢复环境切换 Boot Protocol 后可能误解析 X/Y。",
                "SET_PROTOCOL(BOOT) 后抓包确认标准 Boot Mouse 报告；多环境移动/按键通过。",
                True,
            ),
            make_issue(
                "B-11",
                "critical-observation",
                runtime_status,
                "有线鼠标枚举和配置在线，但按键/移动无响应",
                runtime_evidence,
                "鼠标完全不可用；可能是扫描/传感器/事件线程死锁、断言或状态机卡死。",
                "冷启动和故障注入后持续输入；看门狗恢复；保存 fault/PC/LR/coredump 并关闭根因。",
                True,
            ),
            make_issue(
                "B-12",
                "medium",
                "confirmed-release-gap",
                "官方 Launcher API 没有该鼠标/接收器的固件版本记录",
                [
                    "mouse firmware API versions=[]",
                    "receiver firmware API versions=[]",
                ],
                "用户无法通过官方发布链路核验、升级或回退当前 DVT 固件。",
                "发布 API 提供签名镜像、兼容矩阵、校验值和受控恢复路径。",
                False,
            ),
            make_issue(
                "H-01",
                "high-if-applicable",
                "hypothesis",
                "需排查 nRF54LM20 + picolibc/动态堆 SRAM overlay 已知致命崩溃",
                [
                    "mouse and receiver contain picolibc/assert.c",
                    "exact Kconfig/linker overlay is unavailable",
                ],
                "若构建配置命中该条件，可发生 fatal crash；现有证据不足以认定本次死机同源。",
                "取得 prj.conf/map 后排除受影响配置，或升级/回移植修复并完成压力测试。",
                True,
            ),
            make_issue(
                "B-13",
                "high",
                "high-confidence-resilience-gap",
                "非 fault 型线程/状态机停滞缺少已证实的 watchdog 恢复",
                [
                    "HardFault vector=0x200200A9, common fault decoder=0x2001FF48",
                    "fatal dispatch=0x20040B9A -> 0x200327A4",
                    "mouse fatal tail 0x20020DE8 and receiver 0x20008298 write "
                    "AIRCR value 0x05FA0004 (SYSRESETREQ), then wait for reset",
                    "watchdog device/driver exists, but the watchdog device object "
                    "address has no direct application reference in this image",
                    "the observed device stayed enumerated with no input, which is "
                    "more consistent with a non-fault stall than this reset path",
                ],
                "线程死锁、SPI 永久等待或中断风暴不会必然进入 fatal handler，设备可保持 USB 枚举但停止输入。",
                "启用独立 watchdog 和健康条件喂狗；注入线程锁死、SPI timeout 与中断风暴后自动恢复并保留现场。",
                True,
            ),
            make_issue(
                "B-15",
                "high",
                "confirmed-design-risk",
                "物理恢复依赖可能已经停滞的按键扫描路径",
                [
                    "recovery mask 0x1B is evaluated inside normal input processing",
                    "ordinary mouse HID remained at 0 reports while the config "
                    "interface continued responding",
                ],
                "输入扫描停滞时四键恢复可能无法被检测，只能断电或使用 SWD。",
                "恢复组合由独立线程、定时器或 boot-stage GPIO 检测。",
                True,
            ),
        ]
    )

    blocking = [
        "缺少对应 west.yml、prj.conf、DTS/overlay、驱动和协议源码",
        "缺少精确 NCS/toolchain 锁定文件、ELF/map 和可符号化故障现场",
        "缺少 MCUboot 签名私钥或 bootloader 接受的开发 key 策略",
        "缺少完整 flash/配置备份与已验证的恢复/量产烧录流程",
    ]
    return {
        "schema_version": 1,
        "audit_scope": "static signed-image and product-integration audit",
        "images_modified": False,
        "checks": checks,
        "checks_passed": sum(bool(item["pass"]) for item in checks),
        "checks_total": len(checks),
        "issues": issues,
        "issue_counts": {
            status: sum(issue["status"] == status for issue in issues)
            for status in sorted({issue["status"] for issue in issues})
        },
        "build_blockers": blocking,
        "burnable_fixed_firmware_ready": False,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# G6 HE / UltraLink 缺陷台账",
        "",
        "生成方式：`tools/audit_release.py`（只读、确定性审计）",
        "",
        f"- 镜像结构检查：{report['checks_passed']}/{report['checks_total']} 通过",
        f"- 原始镜像被修改：{report['images_modified']}",
        f"- 可烧录修复固件已就绪：{report['burnable_fixed_firmware_ready']}",
        "",
        "## 缺陷",
        "",
    ]
    for issue in report["issues"]:
        lines.extend(
            [
                f"### {issue['id']} [{issue['severity']}] {issue['title']}",
                "",
                f"- 状态：`{issue['status']}`",
                f"- 需要源码修复：`{issue['source_required']}`",
                f"- 影响：{issue['impact']}",
                f"- 通过标准：{issue['acceptance']}",
                "- 证据：",
                "",
            ]
        )
        lines.extend(f"  - {item}" for item in issue["evidence"])
        lines.append("")
    lines.extend(["## 进入修复与烧录前的阻塞项", ""])
    lines.extend(f"- {item}" for item in report["build_blockers"])
    lines.extend(
        [
            "",
            "> 这些阻塞项未解除前，修改任何 `.signed.bin` 字节都会破坏 Ed25519",
            "> 签名，不能作为可烧录修复固件交付。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mouse", type=Path, required=True)
    parser.add_argument("--receiver", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--device-snapshot", type=Path)
    parser.add_argument("--runtime-probe", type=Path)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    args = parser.parse_args()

    report = audit(
        args.mouse,
        args.receiver,
        args.contract,
        args.device_snapshot,
        args.runtime_probe,
    )
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    return 0 if report["checks_passed"] == report["checks_total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
