# Keychron Windows 鼠标固件升级器分析

日期：2026-07-23  
对象：Keychron G6 HE 鼠标 `3434:D086`  
升级器：`Keychron_Bt_Firmware_Upgrade_v1.02.exe`

## 结论

官网 Windows 升级器提供了此前实机 DFU 尝试缺少的关键状态顺序：

```text
应用态 D086
  -> 0x61 查询升级能力
  -> 若 bootloader_switch 字节非 0，立即发送 0x67
  -> 等待 3434:D000 / Usage Page 008C / Usage 0001
  -> 在 D000 Bootloader 中重新读取并核对型号
  -> 0x61 查询 DFU 版本
  -> 0x62 设置升级模式
  -> 0x63 启动升级
  -> 0x64 分包写入
  -> 0x65 校验
  -> 0x66 切换并复位
```

此前的实机尝试是：

```text
0x61 -> 0x62 -> 0x63 无响应 -> 再测试 0x67
```

两者不是同一条状态路径。官网程序不会在当前 G6 的 D086 应用态直接执行
`0x62/0x63`；它先根据 `0x61` 的能力字节进入独立 D000 Bootloader。

因此，“D086 应用态的 0x63 无响应”目前不能证明 D000 Bootloader 的 DFU
也不可用。下一次测试应严格复刻官网顺序。

## 官网资料

- 官方通用无线鼠标升级说明：
  <https://www.keychron.com/pages/how-to-flash-the-firmware-and-factory-reset-the-keychron-wireless-mice>
- 官方固件入口：
  <https://www.keychron.com/pages/firmware>
- 官方 Windows 升级器：
  <https://cdn.shopify.com/s/files/1/0059/0630/1017/files/Keychron_Bt_Firmware_Upgrade_v1.02.exe?v=1730100690>

官网说明要求：

- Windows 系统；
- 鼠标使用数据线连接；
- 同一时间只连接一只目标鼠标；
- 先 `Get Version`，再选择固件，最后 `Update`；
- 鼠标与接收器固件分别升级。

当前通用说明列出了 M 系列鼠标，没有列出 G6 HE。G6 HE 固件文件也没有在公开
官网固件页检索到。此处只能确认升级器的通用 HID 协议能识别 G6 HE 的接口，不能
据此声称 G6 HE 已获得公开官网升级支持。

## 升级器文件证据

本地文件：

`vendor/keychron-windows-updater/Keychron_Bt_Firmware_Upgrade_v1.02.exe`

- 文件大小：约 2.1 MB
- 类型：PE32 GUI，x86 Windows 原生程序
- SHA-256：
  `432480917a0f746c3c1ce7910d62b98ea239a22e17f40a1e6307cde1fb923f4a`
- 产品版本：`V1.02`
- PE 时间戳：2024-10-23
- 未发现 Authenticode Security Directory
- 导入 `HID.DLL`、SetupAPI、`CreateFileW`、`ReadFile`、`WriteFile`
- PDB 路径：
  `D:\MyCode\Keychron Bluetooth HID Firmware Update\Bin\Keychron Bt Firmware Upgrade_Release.pdb`

内嵌状态文本包括：

- `Switching to bootloader...`
- `Bootloader connected`
- `Switch to bootloader timeout`
- `Bootloader model: %s: file: %s`
- `Incorrect bootloader`
- `Unknown protocol version`
- `Unknow DFU version`
- `Set update mode failed`
- `Update started, don't remove USB cable during update`
- `Update completed`

这些文本和控制流共同证明升级器不是简单地把 `.bin` 直接写给当前应用接口。

## HID 目标筛选

升级器只接收 Keychron VID `3434`，并把设备分为三类：

| 类型 | PID / Usage Page / Usage | 用途 |
|---|---|---|
| 1 | `D000 / 008C / 0001` | 独立 Bootloader |
| 2 | 非 `D0xx / FF60 / 0061` | 旧式升级通道 |
| 3 | 非 `D000 / 008C / 0001` | 新式应用态升级通道 |

当前 G6 HE：

- VID/PID：`3434:D086`
- 升级接口：Usage Page `008C`、Usage `0001`、interface 3
- HID 输出报告：33 字节，Report ID `B2`
- HID 输入报告：33 字节，Report ID `B1`
- 被官网升级器归类为类型 3

升级器发送 `0x67` 后只等待类型 1，即 `3434:D000`。如果 D000 没有出现，
程序最终显示 `Switch to bootloader timeout`。

## 当前 G6 的只读能力响应

2026-07-23 在唯一匹配的 G6 HE 上只读发送 `0x61`，收到：

```text
AA 55 09 F6 03 A3 01 61 00 01 00 01 07 01 ...
```

升级器解析出的四个能力字节为：

```text
01 00 01 07
```

其中最后一个字节 `07` 非零。升级器主状态机因此选择：

```text
0x61 -> 0x67 -> 等待 D000
```

而不是在 D086 中直接执行 `0x62/0x63`。

## 线协议

G6 HE 的官网升级通道与 Launcher 的 64 字节配置通道不同：

- 官网升级器：Usage Page `008C`，33 字节；
- Launcher/配置：Usage Page `FFC1`，64 字节。

官网升级器在类型 1/3 设备上使用以下外层帧：

```text
B2 AA 55 LEN ~LEN SEQ PAYLOAD... CHECKSUM_LE16...
```

例如 `0x67` 的 33 字节报告起始为：

```text
B2 AA 55 03 FC <SEQ> 67 67 00 ...
```

`0x61` 响应的内层有效负载以 `A3 <SEQ> 61` 开始。

主要操作码：

| 操作码 | 作用 |
|---|---|
| `0x60` | 读取设备型号与版本 |
| `0x61` | 读取协议、DFU 和切换能力 |
| `0x62` | 设置升级模式 |
| `0x63` | 启动升级 |
| `0x64` | 写入数据，主体按 16 字节分块 |
| `0x65` | 校验 |
| `0x66` | 切换/完成并复位 |
| `0x67` | 从应用态切换至 Bootloader |

## 对现有结论的修正

旧结论：

> 当前直连 HID 通道无法完成原厂签名包重刷。

更准确的结论：

> 已验证在 D086 应用态先执行 `0x62/0x63` 无法启动写入；尚未按官网程序的
> 精确顺序验证“复位后的 D086 -> 0x61 -> 立即 0x67 -> D000”路径。

此前确实发送过格式正确的 `0x67`，但它是在 `0x62/0x63` 尝试之后发送。
应用态可能已经处于不接受 Bootloader 切换的中间状态。因此 D000 路径仍有一个
明确、可验证的剩余实验。

## 下一步修改方案

修改现有 `tools/flash_g6_dfu.py`：

1. 唯一锁定 `3434:D086 / 008C:0001 / interface 3`；
2. 先执行 `0x66` 或物理重新插拔，确保状态干净；
3. 只读执行 `0x60` 与 `0x61`；
4. 若 `bootloader_switch != 0`，立即发送 `0x67`，此时不先发送 `0x62`；
5. 监控 `3434:D000 / 008C:0001`；
6. D000 出现后重新执行 `0x60`，将 Bootloader 型号与固件文件型号比较；
7. 重新执行 `0x61` 并检查 DFU 版本与升级模式；
8. 只有前述检查均通过，才发送 `0x62/0x63`；
9. `0x63` 成功后才允许进入 `0x64` 写入循环；
10. 保存完整收发帧、枚举时间线和最终版本回读。

如果严格顺序下 D000 仍不出现，则问题可收敛为以下之一：

- 当前 DVT 应用固件的 `0x67` 实现缺陷；
- Bootloader 缺失、损坏或被构建配置禁用；
- Bootloader 入口另有硬件条件；
- 当前固件的 capability `07` 与实际 Bootloader 能力不一致。

