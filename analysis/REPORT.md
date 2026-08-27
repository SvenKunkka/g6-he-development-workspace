# Keychron G6 HE / UltraLink 固件首轮审计

审计日期：2026-07-23  
审计方式：文件静态分析 + macOS USB/HID 只读枚举  
安全边界：首轮为纯静态/枚举分析；死机复查阶段只发送了官方 Launcher 的只读协议
探针。没有发送 DFU、配对、擦除、恢复出厂或配置写入命令。

> 本文件保留首轮结论。后续反汇编已经确认 bond 子树调用、双传感器 profile 和
> fault reset 路径，并增加了死机现场只读探针；最新权威结果请以
> `analysis/BUG_LEDGER.md`、`analysis/release_audit.json` 和
> `analysis/REVERSE_ENGINEERING.md` 为准。

## 结论摘要

- 两份文件都不是“裸 bin”，而是结构完整的 MCUboot 签名镜像。
- 镜像正文未加密，CPU 目标为 nRF54LM20A 的 Arm Cortex-M33 / Thumb-2。
- 两份镜像的长度、版本、编译日期和内部 SHA-512 均自洽，未发现下载损坏。
- 两份镜像都使用同一个 64 字节公钥哈希，并携带 Ed25519 签名；由于没有公钥，
  本次只能验证镜像内 SHA-512，不能独立验证 Ed25519 签名真伪。
- 量产镜像不可直接修改后刷入：任意字节变化都会破坏签名。DIY 固件还需要源码、
  板级配置，以及开发签名/解锁 bootloader/受控调试入口中的至少一种。
- 后续 Launcher 协议复查新增 2 个已确认的规格/配置不一致，并记录 1 个待冷启动
  复现的运行时卡死观察；仅凭二进制还不能诚实地宣称完成全部逻辑 Bug 审计。

## 文件身份与完整性

| 项目 | G6 HE 鼠标 | UltraLink 接收器 |
|---|---:|---:|
| 文件 | `G6HE_v1.0.0+5_20260722.signed.bin` | `UltraLink_dongle_rx21_v1.2.1_1_20260721.signed.bin` |
| 文件大小 | 342,957 B | 120,929 B |
| SHA-256 | `b77f21d0d28fc9315f4b667e2e24046b49ad9e480749a21a9888e989cfe85ce0` | `c3b27594a7f636ef0324d61a61a018511209ff2de59104e1e1bb6eaa6021a1cf` |
| MCUboot 版本 | 1.0.0+5 | 1.2.1+1 |
| 编译时间（镜像字符串） | 2026-07-22 12:15:04/07 | 2026-07-21 18:47:30/32 |
| Header | 2,048 B | 2,048 B |
| 正文 | 340,696 B | 118,668 B |
| 加载地址 | `0x20000800` | `0x20000800` |
| 标志 | `RAM_LOAD` | `RAM_LOAD` |
| TLV 总长 | 213 B | 213 B |
| 签名元数据 | SHA-512、SIG_PURE、KEYHASH、Ed25519 | 同左 |
| 内部 SHA-512 | 匹配 | 匹配 |
| Security Counter | 缺失 | 缺失 |
| Dependency TLV | 缺失 | 缺失 |

两个 KEYHASH 完全相同：

`77f8944a6057fdf3ada448a19561f71a536754885dd95f277edd6a1755d757a29ce7bf820140c086dd000a9bae9741dc9403746fe6364af3fb2593cf8f0121ee`

接收器还暴露了构建栈：

- nRF Connect SDK `v3.3.0-ba167d9f3db4`
- Zephyr `v4.3.99-fd9204a02d52`
- 应用构建标识 `v1.0.0-47c95352b7e6`

这里的应用构建标识不是发布固件版本；发布版本仍是 `1.2.1+1`。

## 鼠标规格基线

以下来自 2026-07-13 调查口径的 Keychron 韩国官方产品简报；页面标注产品预计
2026 年 9 月初上市，因此当前固件属于上市前版本，规格仍可能变化。用户提供的是
UltraLink 接收器，对应内置电池版。

| 项目 | 规格 |
|---|---|
| SoC | Nordic nRF54LM20A，128 MHz Cortex-M33，2 MB NVM / 512 KB RAM |
| 传感器 | PixArt PAW3955 |
| DPI | 1–40,000，最小 1 DPI 步进 |
| 跟踪 | 750 IPS / 60 G |
| LOD | 0.7–1.7 mm，5 档 |
| Sensor frame rate | 13K / 20K fps |
| 回报率 | 有线与 2.4 GHz 最高 8,000 Hz |
| 连接 | Bluetooth 5.3 / 2.4 GHz / USB 有线 |
| 主按键 | MagOptic，0.6 mm 总行程，12 档触发，左右独立 |
| Rapid Trigger | 11 档动态触发/复位 |
| 按键寿命/力度 | 1 亿次 / 60 ±10 gf |
| 滚轮 | 24 段光学编码器 |
| 尺寸 | 123.7 × 63 × 41 mm |
| 重量 | 内置电池 40 ±3 g；可换电池版 46 ±3 g |
| 电池系统 | 4.4 V 高压电池；内置版配 UltraLink |

## 真机枚举

首轮枚举同时看到了鼠标和接收器：

| 设备 | VID:PID | bcdDevice | USB | HID 间隔 | 序列号 |
|---|---|---:|---:|---:|---|
| Keychron G6 HE | `3434:D086` | `1.00` | 480 Mbps | 125 µs | 无 |
| Keychron UltraLink | `3434:D05B` | `1.21` | 480 Mbps | 125 µs | `6B42451EFF74B72C` |

G6 HE 暴露 4 个 HID 接口：

- Mouse：8 B 输入，125 µs；
- Keyboard/Consumer：9 B 输入；
- 厂商页 `0xFFC1`：64 B 输入/输出；
- DFU/升级页 `0x008C`：33 B 输入/输出。

鼠标报告包含 5 个按钮、垂直滚轮、水平滚动以及 16 位 X/Y。125 µs 与 8,000 Hz
上限相符。

后续复查时，UltraLink 已从 USB 树中消失，只剩有线连接的 G6 HE。用户随后确认是
主动拔掉接收器，因此不属于固件掉线 Bug。

## Bug / 风险清单

### F-08 高：G6 HE 的 Launcher 协议档位与 8K / 20K 规格不一致

证据：

- Launcher 产品 API 将 `3434:D086` 正确识别为 Keychron G6 HE；
- 真机配置接口是 Usage Page `0xFFC1`，Launcher 因而选择 `1k` Feature Report
  协议；
- 该协议的基础信息结构只返回 3 个回报率档位，Launcher 对应实现只写
  `125 / 500 / 1000 Hz`；
- 同一协议的 `0x42` 传感器指令没有 20K FPS 字段，并明确构造
  `fps20kSupport: false`；
- 但产品规格为最高 8,000 Hz 和 13K/20K sensor FPS，Launcher 的 G6 HE 静态 JSON
  也列出最高 8,000 Hz。

影响：当前 `v1.0.0+5` 与 Launcher 的组合无法通过公开配置协议安全开放 2K/4K/8K
回报率与 20K FPS。若 UI 强行显示并写入，可能写错字段或造成配置损坏。

判定：协议/规格不一致已确认。根因可能是固件暴露了错误 Usage Page、Launcher 将
新机型绑定到旧 `1k` 协议，或 DVT 固件尚未合入 8K Nordic 参数协议；需固件源码和
Launcher 产品配置共同修复。

### F-09 中：Launcher 的 G6 HE 静态配置与产品规格再次漂移

证据：`/static/device/875876486/json/v3.json` 把 DPI 限制写为
`50–30000`，LOD 只列 `0.7 / 1.0 / 2.0 mm` 三档；官方产品简报写的是
`1–40000 DPI`、`0.7–1.7 mm` 五档。

影响：即便鼠标固件支持完整硬件范围，Launcher 也会截断 30K 以上 DPI，并无法选择
五档 LOD；反过来，如果 DVT 固件确实只支持 JSON 中的范围，产品规格与量产能力不符。

判定：配置漂移已确认；哪一侧是最终量产口径仍需产品/固件负责人确认。

### F-01 中：两份镜像都没有防回滚 Security Counter

证据：TLV 只有 `SHA512 / SIG_PURE / KEYHASH / ED25519`，没有 MCUboot
`SECURITY_COUNTER (0x50)`。

影响：如果 bootloader 只验证签名、没有在受保护存储中另做单调版本控制，旧的合法
签名镜像可能被降级安装，重新引入旧漏洞。

判定：元数据缺失已确认；是否可实际降级需要 bootloader 策略和受控降级测试。
接收器中存在 `find_slot_with_highest_version` 字符串，说明它可能另有版本选择逻辑，
但这不等价于硬件支持的单调防回滚。

### F-02 中：鼠标和接收器没有声明固件依赖关系

证据：两份镜像都没有 MCUboot `DEPENDENCY (0x40)` TLV。

影响：升级器无法仅凭镜像元数据阻止“不兼容的鼠标版本 + 接收器版本”组合。无线包
格式、配对状态机或 Launcher 协议变化时，单边升级可能造成掉线或无法配置。

判定：依赖元数据缺失已确认；当前 `1.0.0+5 + 1.2.1+1` 是否存在协议不兼容，仍需
协议抓取或源码确认。

### F-03 中低：G6 HE USB 设备没有唯一序列号

证据：真机 `iSerialNumber = 0`，HID API 返回空序列号；UltraLink 则有 16 位十六进制
序列号。

影响：同一台主机连接多只 G6 HE 时，Launcher、DFU 工具和自动化脚本难以稳定区分
设备，通常只能依赖易变化的端口位置或系统路径，增加刷错目标的概率。

建议：量产阶段使用芯片唯一 ID 派生稳定 USB 序列号，并让正常模式与 bootloader
模式保持同一身份关联。

### F-04 中（高疑点）：鼠标镜像固化了 `ppt_ptx/bond/(null)` 设置键

证据：正文偏移 `0x4EBC3` 存在完整 NUL 结尾字符串
`ppt_ptx/bond/(null)`；同一镜像另有正常命名空间 `ppt_ptx/bond`。

影响：这像是空设备名/空索引被格式化进持久化键名。若多 bond、多模式或恢复流程
共用该键，可能造成覆盖、读取不到配对信息、重启后丢配对。

判定：异常字面量已确认；必须通过源码交叉引用或“配对—断电—切换模式—恢复”
矩阵验证，才能升级为已确认功能 Bug。

### F-05 中低（条件性）：接收器保留了可泄漏 RF/bond 信息的详细日志

证据：镜像包含 `Access code: 0x%08x`、`Bond[%d] ... acc=0x%08x`、
`PAIR_REQ ... VID/PID/rssi`、当前/待选信道等日志。

影响：若量产机 UART/RTT/调试日志仍可读，会泄漏无线接入码、配对状态和跳频信息，
降低协议逆向和伪造门槛；同时增加固件体积。

判定：日志代码/格式串存在已确认；量产日志级别、调试口锁定状态尚未验证。Access
Code 本身不是加密密钥，不能据此宣称无线链路已被攻破。

### F-06 低（兼容性待测）：Boot Mouse 声明与 8 字节 Report 布局需要验证

证据：鼠标接口声明 Boot Mouse（Subclass 1 / Protocol 2），Report Protocol 的 8 字节
布局在 X/Y 前插入厂商字节、水平滚动和滚轮字段。

影响：如果收到 `SET_PROTOCOL(BOOT)` 后仍发送此 8 字节布局，而不是标准 Boot Mouse
布局，某些 BIOS、KVM、恢复环境会把字段误认成 X/Y。

判定：当前 macOS Report Protocol 工作正常；必须在不修改设备设置的测试主机上验证
Boot Protocol 切换后才能确认。

### F-07 低：量产镜像暴露较多内部实现信息

证据：保留大量 Zephyr/Nordic 源路径、模块名、断言文本、DFU 状态机和错误路径；
鼠标还保留 `CMAKE_SOURCE_DIR/src/user_ble.c`。

影响：便于攻击者定位 SDK 版本、模块和错误处理路径，也带来只读数据体积开销。

建议：量产 profile 关闭不需要的日志/断言和路径信息，同时保留最小化、可控的故障
遥测。

### OBS-01 已解释：接收器在审计过程中从 USB 树消失

用户确认接收器是主动拔除，不计入固件 Bug。

### OBS-02 待复测：有线 G6 HE 枚举在线但按键/移动无响应

用户现场报告鼠标在光微动模式下完全无输入。macOS 仍持续枚举 4 个 HID 接口，
Mouse 接口的 `InputReportCount` 固定在 `9760`，USB 位置与设备身份未变化。

这符合“固件应用/输入扫描路径卡死，但 USB 枚举层仍存活”的现象，不过静止鼠标本来
就可能不增加报告计数，且正确的 WebHID Feature Report 握手尚未取得用户设备授权，
所以暂列观察，不冒充已定位根因。下一步必须先做完整冷启动，再复测输入计数、按键与
只读握手；冷启动仍无效时保存系统日志和调试口现场。

## 首轮未发现的问题

- 文件截断、Header/TLV 长度错位；
- 文件名版本与 MCUboot Header 版本漂移；
- 文件名日期与内置编译日期漂移；
- 镜像内部 SHA-512 不匹配；
- 鼠标与接收器使用不同签名 KEYHASH；
- 8K 设备却只声明 1 ms USB HID 间隔。

这些结论不代表业务逻辑无 Bug，也不替代签名公钥验证、源码审计和真机压力测试。

## 已准备的分析环境

- Python 3.12 虚拟环境：`.venv`
- Python 库：Capstone、Construct、Cryptography、hidapi、pyelftools
- Arm 工具链：`arm-none-eabi-objdump 2.45.1`
- 固件检查器：`tools/inspect_firmware.py`
- 只读设备枚举器：`tools/enumerate_keychron_hid.py`
- 机器可读结果：`analysis/firmware_report.json`
- 当前设备快照：`analysis/connected_devices.json`
- 仅用于分析的正文副本：`analysis/extracted/*.body.bin`

原始 `.signed.bin` 没有被修改。

## DIY 进入下一阶段前的硬门槛

1. 找到与 `54LMG6HE` / `54L2DNGC` 对应的源码、DTS/overlay、Kconfig 和 west manifest；
2. 取得 bootloader 的签名策略与公钥，确认是否支持开发 key；
3. 确认 SWD/调试口是否锁定、是否有官方恢复模式；
4. 在任何写入前唯一识别目标，读取完整 flash/配置区备份并验证可恢复；
5. 建立鼠标 × 接收器兼容矩阵，以及有线、2.4G、BLE、8K、休眠/唤醒、DFU 回滚测试。

在这些条件未满足前，不应尝试修改量产镜像后直接刷入。

## 外部规格依据

- Keychron 韩国官方 G6 HE 产品简报：
  <https://keychron.kr/news/g6-he-brief/>
- Nordic nRF54LM20A 产品页：
  <https://www.nordicsemi.com/Products/nRF54LM20A>
- Nordic Cortex-M33 CPU 文档：
  <https://docs.nordicsemi.com/r/bundle/ps_nrf54lm20a/page/cpu.html>
- MCUboot 镜像/TLV 定义：
  <https://github.com/mcu-tools/mcuboot/blob/main/boot/bootutil/include/bootutil/image.h>
