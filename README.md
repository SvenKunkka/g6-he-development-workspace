<!-- SVENKUNKKA-README-NAV:BEGIN -->
[中文项目说明](#project-overview-zh) · [English overview](#project-overview-en) · [维护者 X / Maintainer on X](https://x.com/Svenu1s5)
<!-- SVENKUNKKA-README-NAV:END -->

# G6 HE firmware lab

This workspace contains the signed-image audit, read-only live probes, a
clean-room replacement firmware, and a WebHID control page. The original images
remain immutable. The only live configuration write attempted during diagnosis
was the official DPI-default command; immediate readback showed no change, so
the tool stopped without retrying.

## Environment

```sh
/opt/homebrew/bin/python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

The machine also has `arm-none-eabi-objdump` for Cortex-M33/Thumb-2
disassembly.

## Repeat the inspection

```sh
.venv/bin/python tools/inspect_firmware.py \
  "<G6_FIRMWARE_DIR>/G6HE_v1.0.0+5_20260722.signed.bin" \
  "<G6_FIRMWARE_DIR>/UltraLink_dongle_rx21_v1.2.1_1_20260721.signed.bin" \
  --output analysis/firmware_report.json \
  --extract-dir analysis/extracted

.venv/bin/python tools/enumerate_keychron_hid.py \
  --output analysis/connected_devices.json

.venv/bin/python tools/probe_g6_config_readonly.py \
  --output analysis/live_config.json
```

The extracted bodies are copies for analysis. The original signed files remain
untouched.

## Key findings

- `analysis/OFFICIAL_WINDOWS_UPDATER_ANALYSIS_20260723.md` documents the
  official Windows updater, its HID target rules, the `D086 -> D000`
  bootloader transition, and the corrected DFU test order.
- `analysis/DFU_FLASH_ATTEMPT_20260723.md` records the earlier live DFU attempt
  and links to the corrected interpretation.
- `analysis/LIVE_RECOVERY_RESULT_20260723.md` records the live configuration
  recovery and the remaining zero-input-report failure.
- `analysis/DVT_TEST_ISSUES_20260723.md` and
  `analysis/dvt_test_issues_20260723.json` contain the 20 DVT issues supplied
  by the test team, with repair work packages and acceptance criteria.

## Safety boundary

The signed images use MCUboot SHA-512 plus Ed25519 signatures. Editing any
signed byte invalidates the signature. Do not attempt a write until the exact
bootloader policy, recovery path, debug lock state, unique hardware target, and
full backup are known.


---

<!-- SVENKUNKKA-PROJECT-INFO:BEGIN -->

<a id="project-overview-zh"></a>
## 中文项目说明

G6 HE 固件研究工作区，包含签名镜像检查、只读 HID 探测、DFU 与恢复分析、DVT 问题整理，以及洁净室固件和 WebHID 研究材料。

**使用入口：** 按照 README 创建 Python 环境并安装 `requirements.txt`；从 `tools/inspect_firmware.py`、`tools/enumerate_keychron_hid.py` 和 `tools/probe_g6_config_readonly.py` 开始检查。

**范围说明：** 需自行提供匹配的固件输入；修改签名字节会使签名失效。已有恢复记录仍保留零输入报告问题，不能将研究材料视为修复完成或正式可刷写版本。

<a id="project-overview-en"></a>
## English project overview

A G6 HE firmware research workspace containing signed-image inspection, read-only HID probes, DFU and recovery analysis, DVT issue tracking, and clean-room firmware and WebHID research materials.

**Getting started:** Create the Python environment and install `requirements.txt` as documented. Start with `tools/inspect_firmware.py`, `tools/enumerate_keychron_hid.py` and `tools/probe_g6_config_readonly.py`.

**Scope:** Matching firmware inputs must be supplied separately; changing signed bytes invalidates the signature. Recovery records still describe a zero-input-report issue, so research materials should not be treated as a completed fix or an official flashable release.

**仓库维护者 / Repository maintainer:** [SvenKunkka](https://github.com/SvenKunkka) · [X / Twitter](https://x.com/Svenu1s5)

<!-- SVENKUNKKA-PROJECT-INFO:END -->
