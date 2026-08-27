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
