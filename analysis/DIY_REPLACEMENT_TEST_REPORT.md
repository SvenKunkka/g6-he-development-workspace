# G6 HE 自研替代固件验证报告

日期：2026-07-23  
目标：nRF54LM20A CPUAPP / G6 HE 光微动有线模式

## 结论

- clean-room Zephyr 4.4.0 替代固件已完成并可重复编译；
- WebHID 控制页已实现 DIY `3434:D687` 与原厂 `3434:D086` 双协议；
- 量产 `0x6E` 传感器初始化表已与原始签名镜像逐字节核对；
- 三轮主机侧验证全部通过；
- 当前没有执行实机写入：已连接鼠标只有 4 个 HID 接口，没有 DFU、串口、
  J-Link、CMSIS-DAP 或其他可读取完整 RRAM 的通道，因此还不能先做原机备份。

## 本轮发现并修复的替代固件问题

### R-01 [critical] USB 启用后设置 HID 回报周期会启动即 panic

- 原因：Zephyr `hid_device_set_in_polling()` 在 HID 类已初始化后返回
  `-EBUSY`，旧初始化路径把该返回值当致命错误。
- 修复：在 `g6_usb_init()` / `usbd_enable()` 之前设置初始端点周期。
- 验证：源码顺序合同检查、完整 clean build 通过。

### R-02 [high] 运行中只改变量不能改变主机已枚举的 USB 端点周期

- 原因：125–8000 Hz 是 USB 描述符属性，主机枚举后不能原地改变。
- 修复：配置响应完成 250 ms 后依次执行 disable、shutdown、设置周期、
  init、enable；页面等待重枚举并只重连唯一的 `3434:D687`。
- 验证：构建合同检查该调用顺序；网页测试检查重枚举和唯一目标保护。

### R-03 [medium] 传感器成功恢复后可能保留历史 SPI 失败计数

- 影响：新一次偶发传输错误可能过早把已恢复传感器再次隔离。
- 修复：完整启动和 DPI 写入成功后清零 `spi_failures`。
- 验证：`-Wall -Wextra -Werror` 主机测试与 ARM clean build 通过。

## 三轮验证

### 第一轮：协议与外设资产

- `verify_reverse_engineered_assets.py`：PASS；
- `test_config.c`：PASS；
- 传感器 `0x6E` 536 B 初始化表与 8 B post 表逐字节一致；
- Zephyr 完整编译：PASS；
- 页面服务端渲染与 WebHID 目标保护：2/2 PASS。

### 第二轮：框架源码审计与修复

- 对照 Zephyr `usbd_hid.c` 确认 `HID_DEV_CLASS_INITIALIZED` 后返回
  `-EBUSY`；
- 修复 R-01、R-02、R-03；
- 固件 clean build：PASS；
- 页面 build、2 项测试、ESLint：PASS。

### 第三轮：最终可重复构建

- 固件再次 `--pristine` clean build：PASS；
- Flash：87,996 B / 2,036 KB（4.22%）；
- RAM：17,816 B / 511 KB（3.40%）；
- build contract：PASS；
- Intel HEX 地址：`0x00000000–0x000157BB`；
- 初始 SP / reset vector：`0x200035D0 / 0x00002895`；
- 页面 build、2 项测试、ESLint：PASS。

## 最终镜像校验值

- BIN：`a23233f196d8a9b9077538353c3faa1ecc300e6c05e8cb8c4b29e65c19952633`
- HEX：`77ccab53cfc320fc3319b5f7487bef740ada62c8d7dda514641f2066975b8151`
- ELF：`d1951dc5dff2536a4b3e5c5a18caf9d181490602d19b379ca3894d1ea9d24afb`

## 尚未通过的硬件门槛

1. 实机当前仍为原厂 `3434:D086`，4 个接口全部是 HID；
2. 无 USB DFU/CDC，`/dev/cu.*` 只有 macOS 自身端口；
3. 没有检测到 J-Link、CMSIS-DAP、DAPLink 或可确认的 nRF 调试探针；
4. 无法读取完整 RRAM，所以未生成原机可恢复备份；
5. 新镜像是从 `0x00000000` 启动的 SWD standalone image，不是原厂
   Ed25519 签名 MCUboot RAM-load 升级包。

已安装 Homebrew `nrfutil` cask 到 `/opt/homebrew/bin/nrfutil`，二进制带
Nordic Semiconductor ASA Developer ID 签名；但该 cask 已被 Homebrew 标记为
Gatekeeper 不兼容，本机执行 `--version` 持续无输出。没有修改 quarantine 或
绕过 macOS 安全检查。Nordic 官方 `device` 命令支持 J-Link 下的 list、read、
dump-to-file、program、fw-verify 与 reset；实际命令参数将在探针出现后以本机
安装版本的 `--help` 锁定，不预先猜测。

只要出现唯一可确认的 SWD 目标，下一步固定为：读取并校验完整备份、做读取
复测、写入 HEX、复读校验、确认 `3434:D687` 枚举、执行鼠标/传感器/看门狗
测试。当前不向仍在枚举的原厂 HID 发送未知 DFU 或擦除命令。
