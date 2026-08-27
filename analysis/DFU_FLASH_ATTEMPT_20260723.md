# G6 HE 有线 DFU 实机烧录尝试

日期：2026-07-23  
目标：Keychron G6 HE `3434:D086`，usage page `0x008C`，interface 3  
镜像：`G6HE_v1.0.0+5_20260722.signed.bin`

## 镜像与目标

- 唯一匹配的更新接口：1
- 镜像大小：342,957 字节
- SHA-256：`b77f21d0d28fc9315f4b667e2e24046b49ad9e480749a21a9888e989cfe85ce0`
- MCUboot 签名区域 SHA-512 TLV 与镜像计算值匹配
- 烧录工具：`tools/flash_g6_dfu.py`

## 已实际发送

按照 Keychron Launcher 中的 HID DFU 实现执行：

1. `0x61` DFU 握手成功，响应中 Launcher 所取 DFU 版本为 `0`。
2. `0x62` prepare 对目标槽位 `0` 和 `1` 都返回状态 `0`。
3. `0x63` start 使用 DFU 版本 `0` 和兼容版本 `1` 均无响应。
4. 在 `0x63` 无响应后，分别测试版本 `0` 和 `1` 格式的第一个 `0x64`
   数据包，均无 ACK。
5. `0x67` bootloader switch 已发送，但 PID、接口和 USB 枚举均未变化。
6. 通过 `0x66` 系统复位后，在重新枚举后的短窗口再次执行完整流程，仍停在
   `0x63`。

## 结果

- 没有收到任何 `0x63` start ACK。
- 没有收到任何 `0x64` data ACK。
- 未进入 Launcher 定义的写入循环，未执行 `0x65` CRC 验证或 `0x66`
  镜像切换。
- 没有已确认的镜像数据写入；设备最后已通过 `0x66` 复位清除 DFU 准备状态。
- 复位后设备重新枚举为原 PID `D086`，`0x60` 回读仍为：
  - module：`54LMG6HE`
  - firmware：`1.0.0+5`
  - hardware：`54LMv1.0`
- 复位后 3 秒普通鼠标接口捕获仍为 0 个输入报告。

## 结论

这版应用固件保留了 DFU 查询和 prepare 响应，但按本次测试顺序没有进入可传输镜像的
start 状态；继续发送数据只会被忽略，不能形成可校验的烧录。

后续对 Keychron 官方 Windows 升级器的静态分析发现，本次命令顺序与官方状态机不同：
官方程序在 `0x61` 返回 bootloader-switch 标志后，会先执行 `0x67` 并等待
`3434:D000`，之后才在 Bootloader 中执行 `0x62/0x63`。本次是在
`0x62/0x63` 失败后才测试 `0x67`，因此不能据此排除 D000 DFU 路径。

修正后的结论和精确复测方案见
`analysis/OFFICIAL_WINDOWS_UPDATER_ANALYSIS_20260723.md`。

如果严格复刻官网顺序后 D000 仍未出现，能绕过该应用态阻塞的通路才收敛为：

1. 通过板上按键/测试点让 MCU 在上电时直接进入 MCUboot USB recovery；
2. 使用 J-Link/CMSIS-DAP 连接 SWD，直接读写 flash。
