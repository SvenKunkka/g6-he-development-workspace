# G6 HE / UltraLink 缺陷台账

生成方式：`tools/audit_release.py`（只读、确定性审计）

- 镜像结构检查：11/11 通过
- 原始镜像被修改：False
- 可烧录修复固件已就绪：False

## DVT 实机测试输入

测试团队针对 `G6HE_v1.0.0+5_20260722.signed.bin` 提供了 20 项实机问题：

- P0 / critical：8
- P1 / high：8
- P2 / medium：3
- P3 / low：1

完整现象、可能根因、修改方案和逐项验收标准：

- 人类可读：`analysis/DVT_TEST_ISSUES_20260723.md`
- 机器可读：`analysis/dvt_test_issues_20260723.json`

这些记录的证据状态为 `reported-reproduced-by-test-team`。它们是正式修复输入，
但不能仅凭现象把某一段反汇编或某一个源码函数标记为根因已确认。

其中已与现有审计证据形成关联：

- T-13 重置不清除 2.4G 配对、T-16 双接收器回连失败，与 B-03 的错误 bond
  settings 子树高度相关；
- T-17 2.4G 运行中突降至约 24 Hz，与 B-11 输入路径停滞及 B-13 缺少有效
  watchdog 恢复属于同一可靠性范围；
- T-04 至 T-07 表明光/磁扫描、ADC、USB/RF 高回报率调度需要作为一个实时系统
  共同修复，不能只修改 Launcher 档位。

## 缺陷

### B-01 [medium] 两份量产镜像缺少 MCUboot Security Counter

- 状态：`confirmed`
- 需要源码修复：`True`
- 影响：若 bootloader 没有独立单调版本策略，旧的合法签名镜像可能被降级安装。
- 通过标准：两份发布镜像包含有效 SECURITY_COUNTER，且受控降级测试被拒绝。
- 证据：

  - mouse: TLV types=SHA512,SIG_PURE,KEYHASH,ED25519
  - receiver: TLV types=SHA512,SIG_PURE,KEYHASH,ED25519

### B-02 [medium] 鼠标与接收器镜像未声明版本依赖

- 状态：`confirmed`
- 需要源码修复：`True`
- 影响：升级器无法仅凭镜像阻止不兼容的鼠标/接收器版本组合。
- 通过标准：镜像声明并强制执行兼容版本范围，单边不兼容升级测试被拒绝。
- 证据：

  - mouse: DEPENDENCY=False
  - receiver: DEPENDENCY=False

### B-03 [high] 鼠标启动代码加载错误的空标识配对子树

- 状态：`confirmed-binary-call`
- 需要源码修复：`True`
- 影响：启动时读取的子树与注册 handler 根路径不一致，bond 配置可能完全不加载。
- 通过标准：源码改为正确根路径或有效设备 ID；配对、断电、模式切换、恢复矩阵全部通过。
- 证据：

  - mouse body offsets=[322499] string=ppt_ptx/bond/(null)
  - function 0x20018B48 loads literal at 0x20018BDC and calls settings wrapper 0x200402A4
  - registered settings handler root is ppt_ptx/bond (pointer stored at body offset 0x514A8)

### B-04 [medium-low] 接收器镜像保留 RF/bond 详细日志格式

- 状态：`conditional-confirmed`
- 需要源码修复：`True`
- 影响：若 UART/RTT 在量产机可读，会泄漏接入码、配对状态和信道信息。
- 通过标准：发布构建移除敏感日志，或证明调试口锁定且日志不可读取。
- 证据：

  - receiver body offsets=[99232, 99312, 100178]

### B-05 [low] 发布镜像保留源路径与断言实现信息

- 状态：`confirmed`
- 需要源码修复：`True`
- 影响：扩大逆向信息面并占用只读空间。
- 通过标准：release profile 仅保留受控故障码，不包含本机构建路径或无用断言文本。
- 证据：

  - body offsets=[323553, 104556]

### B-07 [medium] Launcher DPI/LOD 范围与产品规格漂移

- 状态：`confirmed-integration`
- 需要源码修复：`True`
- 影响：配置器会截断合法范围，或向不支持的固件写入错误值。
- 通过标准：产品规格、固件能力声明和 Launcher schema 三方一致并通过边界测试。
- 证据：

  - product brief DPI=1-40000
  - official Launcher DPI=50-30000
  - live firmware DPI max=50000, step=1
  - product LOD=[0.7, 1.0, 1.2, 1.5, 1.7]
  - launcher LOD=[0.7, 1.0, 2.0]

### B-08 [high] 固件有两套传感器能力表，但 Launcher 使用单一静态配置

- 状态：`confirmed-binary-profile-drift`
- 需要源码修复：`True`
- 影响：不同传感器 BOM 会被同一个 Launcher 30K/三档 LOD schema 裁剪或错误配置。
- 通过标准：确认 ID 与 BOM 映射；固件上报能力，Launcher 按读取结果生成 DPI/LOD/FPS 控件。
- 证据：

  - 2026-07 product sync=PAW3955
  - 2026-04 electrical/config spec=PAW3950
  - function 0x200158C0 selects profile 0x2004BB20 for sensor ID 0x6E and 0x2004BBA0 for ID 0x53
  - the adjacent D086 profiles contain 40000 and 30000 capability constants respectively

### B-09 [medium-low] G6 HE USB 设备缺少稳定唯一序列号

- 状态：`confirmed-device`
- 需要源码修复：`True`
- 影响：多只设备同时连接时难以唯一选择，增加 DFU 刷错目标风险。
- 通过标准：正常模式与 bootloader 暴露同一稳定、唯一且非隐私敏感的序列号。
- 证据：

  - analysis/connected_devices.json: 3434:D086 serial=null

### B-10 [medium] Boot Mouse 模式的 8 字节报告兼容性未验证

- 状态：`needs-hardware-test`
- 需要源码修复：`True`
- 影响：BIOS、KVM 或恢复环境切换 Boot Protocol 后可能误解析 X/Y。
- 通过标准：SET_PROTOCOL(BOOT) 后抓包确认标准 Boot Mouse 报告；多环境移动/按键通过。
- 证据：

  - USB interface declares Boot Mouse
  - Report Protocol layout includes vendor byte and horizontal wheel

### B-11 [critical-observation] 有线鼠标枚举和配置在线，但按键/移动无响应

- 状态：`runtime-observed-input-path-stall`
- 需要源码修复：`True`
- 影响：鼠标完全不可用；可能是扫描/传感器/事件线程死锁、断言或状态机卡死。
- 通过标准：冷启动和故障注入后持续输入；看门狗恢复；保存 fault/PC/LR/coredump 并关闭根因。
- 证据：

  - User observed complete input freeze in optical-switch mode
  - macOS still enumerated four HID interfaces
  - Earlier InputReportCount snapshot remained 9760
  - Current ReportAvailableCalls was 14434 and stayed unchanged during a two-second static sample (non-conclusive)
  - correct B3/B4 and B5/B6 read-only queries 0x02/0x04/0x06 all responded in 4.1 ms
  - decoded protocol=6, firmware=1.0.0+5, work_mode=0
  - B5/0x0F/0xFF recover-all returned E4 00 0F and reset configuration
  - update-interface 0x66 reset re-enumerated USB but did not restore input
  - v6 DPI, 8K polling, and 20K settings all passed immediate readback
  - three 12-second interface-0 captures received exactly 0 reports

### B-12 [medium] 官方 Launcher API 没有该鼠标/接收器的固件版本记录

- 状态：`confirmed-release-gap`
- 需要源码修复：`False`
- 影响：用户无法通过官方发布链路核验、升级或回退当前 DVT 固件。
- 通过标准：发布 API 提供签名镜像、兼容矩阵、校验值和受控恢复路径。
- 证据：

  - mouse firmware API versions=[]
  - receiver firmware API versions=[]

### H-01 [high-if-applicable] 需排查 nRF54LM20 + picolibc/动态堆 SRAM overlay 已知致命崩溃

- 状态：`hypothesis`
- 需要源码修复：`True`
- 影响：若构建配置命中该条件，可发生 fatal crash；现有证据不足以认定本次死机同源。
- 通过标准：取得 prj.conf/map 后排除受影响配置，或升级/回移植修复并完成压力测试。
- 证据：

  - mouse and receiver contain picolibc/assert.c
  - exact Kconfig/linker overlay is unavailable

### B-13 [high] 非 fault 型线程/状态机停滞缺少已证实的 watchdog 恢复

- 状态：`high-confidence-resilience-gap`
- 需要源码修复：`True`
- 影响：线程死锁、SPI 永久等待或中断风暴不会必然进入 fatal handler，设备可保持 USB 枚举但停止输入。
- 通过标准：启用独立 watchdog 和健康条件喂狗；注入线程锁死、SPI timeout 与中断风暴后自动恢复并保留现场。
- 证据：

  - HardFault vector=0x200200A9, common fault decoder=0x2001FF48
  - fatal dispatch=0x20040B9A -> 0x200327A4
  - mouse fatal tail 0x20020DE8 and receiver 0x20008298 write AIRCR value 0x05FA0004 (SYSRESETREQ), then wait for reset
  - watchdog device/driver exists, but the watchdog device object address has no direct application reference in this image
  - the observed device stayed enumerated with no input, which is more consistent with a non-fault stall than this reset path

### B-15 [high] 物理恢复依赖可能已经停滞的按键扫描路径

- 状态：`confirmed-design-risk`
- 需要源码修复：`True`
- 影响：输入扫描停滞时四键恢复可能无法被检测，只能断电或使用 SWD。
- 通过标准：恢复组合由独立线程、定时器或 boot-stage GPIO 检测。
- 证据：

  - recovery mask 0x1B is evaluated inside normal input processing
  - ordinary mouse HID remained at 0 reports while the config interface continued responding

## 进入修复与烧录前的阻塞项

- 缺少对应 west.yml、prj.conf、DTS/overlay、驱动和协议源码
- 缺少精确 NCS/toolchain 锁定文件、ELF/map 和可符号化故障现场
- 缺少 MCUboot 签名私钥或 bootloader 接受的开发 key 策略
- 缺少完整 flash/配置备份与已验证的恢复/量产烧录流程

> 这些阻塞项未解除前，修改任何 `.signed.bin` 字节都会破坏 Ed25519
> 签名，不能作为可烧录修复固件交付。
