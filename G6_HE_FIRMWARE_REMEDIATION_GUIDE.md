---
schema_version: "1.0"
document_id: "g6-he-firmware-remediation-20260723"
title: "Keychron G6 HE 与 UltraLink 固件缺陷及修改指南"
language: "zh-CN"
generated_at: "2026-07-23T00:00:00+08:00"
document_status: "evidence-backed-analysis"
source_images_modified: false
fixed_signed_images_available: false
machine_manifest: "./analysis/remediation_manifest.json"
authoritative_issue_ids:
  - B-01
  - B-02
  - B-03
  - B-04
  - B-05
  - B-07
  - B-08
  - B-09
  - B-10
  - B-11
  - B-12
  - B-13
  - B-15
  - B-16
  - H-01
---

# Keychron G6 HE 与 UltraLink 固件缺陷及修改指南

## 1. 文档用途

本资料面向三类读者：

1. 用户：快速了解两份固件是否完整、已经确认哪些问题、为什么鼠标仍然无输入。
2. 固件工程师：按优先级实施源码修复、构建、签名、烧录和验收。
3. AI/自动化代理：根据稳定的问题编号、前置条件、动作和验收标准继续执行任务。

本文件是人类可读的主文档。机器可读任务清单位于
`analysis/remediation_manifest.json`。两者使用相同的问题编号。

## 2. 结论摘要

- 两份上传文件都是结构完整的 MCUboot Ed25519 签名镜像，内部 SHA-512 匹配，
  未发现文件截断或下载损坏。
- 原始签名文件没有被修改。直接修改任意已签名字节都会破坏签名。
- 鼠标当前运行版本与上传镜像相同，都是 `1.0.0+5`。
- 鼠标的 USB、配置线程和更新查询仍在线，但普通鼠标输入线程完全无报告。
- 配置恢复、系统复位、8K、20K 和 DPI 回读均不能恢复输入。
- 已执行有线 DFU：`0x61` 查询和 `0x62` prepare 成功，但 `0x63` start、
  `0x64` data 均无 ACK，因此没有完成镜像写入和 CRC 切换。
- 修复死机的最高优先级是：输入链路超时与隔离、独立 watchdog、故障记录、独立恢复
  GPIO、可恢复 DFU。
- 真正交付修复版必须从源码重新构建并使用 bootloader 接受的密钥签名，或通过 SWD
  写入开发镜像；不能在现有 `.signed.bin` 上直接打补丁后量产。

## 3. 输入固件身份

| 角色 | 鼠标 | UltraLink 接收器 |
|---|---|---|
| 文件 | `G6HE_v1.0.0+5_20260722.signed.bin` | `UltraLink_dongle_rx21_v1.2.1_1_20260721.signed.bin` |
| 原始路径 | `<G6_FIRMWARE_DIR>/G6HE_v1.0.0+5_20260722.signed.bin` | `<G6_FIRMWARE_DIR>/UltraLink_dongle_rx21_v1.2.1_1_20260721.signed.bin` |
| 大小 | 342,957 B | 120,929 B |
| SHA-256 | `b77f21d0d28fc9315f4b667e2e24046b49ad9e480749a21a9888e989cfe85ce0` | `c3b27594a7f636ef0324d61a61a018511209ff2de59104e1e1bb6eaa6021a1cf` |
| MCUboot 版本 | `1.0.0+5` | `1.2.1+1` |
| Header / 正文 | 2,048 / 340,696 B | 2,048 / 118,668 B |
| 运行形式 | `RAM_LOAD` | `RAM_LOAD` |
| 签名元数据 | SHA-512、SIG_PURE、KEYHASH、Ed25519 | 同左 |
| 内部 SHA-512 | 匹配 | 匹配 |
| Security Counter | 缺失 | 缺失 |
| Dependency TLV | 缺失 | 缺失 |

两份镜像使用相同 KEYHASH。当前环境没有签名公钥，因此已经确认的是镜像内部
SHA-512 自洽；不能把它表述为“独立完成 Ed25519 真伪验证”。

## 4. 状态与置信度约定

| 状态 | 含义 | AI 是否可直接标记完成 |
|---|---|---|
| `confirmed` | 文件、反汇编、API 或真机结果直接证明 | 仅在修复和验收证据齐全后 |
| `confirmed-binary-call` | 已确认具体二进制调用路径 | 同上 |
| `runtime-observed` | 真机稳定复现，但尚未定位源码根因 | 不可，仅能进入诊断/修复 |
| `design-risk` | 设计路径已确认存在恢复或安全缺口 | 不可，需故障注入验收 |
| `needs-hardware-test` | 静态证据不足，必须真机测试 | 不可 |
| `hypothesis` | 仅为有证据支持的待排查假设 | 不得当作已确认 Bug |

严重度顺序：`critical > high > medium > low`。

## 5. Bug 总表

| ID | 严重度 | 适用对象 | 状态 | 简述 |
|---|---|---|---|---|
| B-11 | critical | 鼠标 | runtime-observed | USB 在线但普通鼠标输入永久停滞 |
| B-03 | high | 鼠标 | confirmed-binary-call | 启动加载错误 bond 子树 |
| B-08 | high | 鼠标 + Launcher | confirmed | 双传感器能力表被单一静态配置覆盖 |
| B-13 | high | 鼠标/接收器 | design-risk | 非 fault 型死锁缺少 watchdog 恢复 |
| B-15 | high | 鼠标 | design-risk | 恢复组合依赖已可能停滞的输入扫描 |
| B-16 | high | 鼠标 DFU | runtime-observed | prepare 成功但 start/data 无响应 |
| B-01 | medium | 两份镜像 | confirmed | 缺少防回滚 Security Counter |
| B-02 | medium | 两份镜像 | confirmed | 缺少鼠标/接收器版本依赖 |
| B-07 | medium | 鼠标 + Launcher | confirmed | DPI/LOD/FPS 规格与配置漂移 |
| B-09 | medium-low | 鼠标 USB | confirmed | 缺少稳定唯一序列号 |
| B-10 | medium | 鼠标 USB | needs-hardware-test | Boot Mouse 报告兼容性未验证 |
| B-12 | medium | 发布系统 | confirmed | 官方固件 API 无当前版本 |
| B-04 | medium-low | 接收器 | conditional-confirmed | 量产镜像保留 RF/bond 敏感日志 |
| B-05 | low | 两份镜像 | confirmed | 保留源路径和断言实现信息 |
| H-01 | high-if-applicable | 两份镜像 | hypothesis | 待排查特定 libc/heap SRAM overlay 崩溃条件 |

## 6. 逐项缺陷与修改方案

### B-11：鼠标输入链路永久停滞

- 严重度：`critical`
- 状态：`runtime-observed`
- 证据：
  - macOS 始终枚举 4 个 HID 接口；
  - 配置命令 `0x02/0x04/0x06/0x49/0x4B/0x65` 正常响应；
  - 配置恢复和 `0x66` 系统复位后仍无输入；
  - 三次各 12 秒及最终 3 秒捕获均为 0 个普通鼠标报告；
  - HE 左右键状态为 `adc_flag=1`，ADC 为 `0/0`。
- 可能根因范围：
  - PAW 传感器 SPI 初始化或事务永久等待；
  - 光磁/HE ADC 扫描或模式切换状态机停滞；
  - 输入事件线程、队列或中断链路死锁；
  - 供电、模式检测脚或硬件信号异常。

修改方案：

1. 所有 SPI/I2C/ADC 等待改为有界超时，返回明确错误码，不允许永久阻塞。
2. 将传感器采集、HE 扫描、USB 报告拆为独立状态机；单一外设失败不得阻塞全部输入。
3. 为事件队列设置上限、丢弃策略和计数器，检测生产者/消费者停滞。
4. 增加 `sensor_reinit()`、`he_reinit()` 和输入线程软重启，不必每次整机复位。
5. 在 retained RAM 或 flash 中保存 reset reason、线程 heartbeat、最后 SPI 状态、
   fault PC/LR/CFSR/HFSR。
6. 光微动、磁微动、混合模式分别建立冷启动和热切换状态机，切换前停止旧采集源，
   清空事件队列，重新校准后再开放输入。

验收：

- 有线/2.4G/BLE 各运行 24 小时，无输入冻结；
- 注入 SPI timeout、ADC 恒零、队列满、中断丢失后 2 秒内恢复；
- 故障发生时仍能输出诊断记录，恢复后移动和五个按键均正常；
- 光/磁模式来回切换至少 10,000 次无冻结。

### B-13：缺少独立 watchdog 健康恢复

- 严重度：`high`
- 状态：`design-risk`
- 证据：fatal 路径会请求 SYSRESETREQ，但未发现应用直接使用 watchdog 设备对象；
  现场现象是 USB 在线而输入停滞，更像非 fault 型死锁。

修改方案：

1. 启用独立硬件 watchdog，不由单一主循环无条件喂狗。
2. 输入、传感器、HE、USB、无线各维护递增 heartbeat。
3. 只有所有必要 heartbeat 在时间窗内推进时才喂狗。
4. watchdog 前先将停滞模块、PC/LR、队列深度和 reset reason 写入 retained 区。
5. 对升级写 flash 阶段设置独立策略，避免正常擦写时间触发 watchdog。

验收：分别锁死每个线程、屏蔽 SPI 完成中断、制造中断风暴；设备必须自动恢复且保留
可区分的故障原因。

### B-15：恢复组合依赖输入扫描

- 严重度：`high`
- 状态：`design-risk`
- 证据：四键恢复掩码 `0x1B` 在普通输入处理路径中检测；当前输入链路停滞时恢复组合
  很可能也无法执行。

修改方案：

1. 在 boot stage 直接读取 GPIO，支持“按住组合键上电进入 recovery”。
2. 运行时恢复检测放入独立低优先级定时器，不依赖主输入队列。
3. 增加测试点或 USB vendor recovery 命令，命令处理不得依赖传感器线程。

验收：人为锁死输入线程后，物理组合和 USB recovery 仍能进入安全恢复模式。

### B-16：DFU prepare 后无法进入 start

- 严重度：`high`
- 状态：`runtime-observed`
- 证据：
  - `0x61` 查询成功，Launcher 解析 DFU version 为 `0`；
  - `0x62` 对目标槽位 0/1 均返回状态 0；
  - `0x63` 使用版本 0/1 均无响应；
  - `0x64` 两种帧格式首包均无 ACK；
  - `0x67` 未触发 Bootloader 枚举；
  - 系统复位后立即重试结果相同。

修改方案：

1. 将 DFU 状态显式定义为 `IDLE -> PREPARED -> STARTED -> WRITING -> VERIFIED ->
   PENDING_SWAP`，任何命令都返回当前状态和错误码。
2. `0x62` 只有在后续 start worker、目标 slot 和 flash driver 均可用时才能返回成功。
3. `0x63` 必须在固定超时内 ACK；后台擦除通过进度事件上报，不得静默等待。
4. 数据包支持序号、重复包幂等、断点查询和最终长度校验。
5. `0x65` 同时校验长度、CRC32、MCUboot SHA-512 和 Ed25519。
6. 提供与应用线程隔离的 MCUboot USB recovery；正常应用死锁时仍可恢复。
7. Bootloader 与应用使用同一稳定设备序列号，确保升级前后可关联。

验收：

- 正常升级、同版本重刷、断线重传、CRC 错误、错误签名、掉电恢复全部通过；
- `0x62` 成功后 `0x63` 必须在 500 ms 内 ACK 或返回错误；
- 任意阶段失败后设备至少能重新进入 USB recovery。

### B-03：错误的 bond settings 子树

- 严重度：`high`
- 状态：`confirmed-binary-call`
- 证据：启动函数实际加载 `ppt_ptx/bond/(null)`，已注册 handler 根路径却是
  `ppt_ptx/bond`。

修改方案：

```c
/* 错误示意 */
settings_load_subtree("ppt_ptx/bond/(null)");

/* 正确方向：根路径必须与注册 handler 一致 */
settings_load_subtree("ppt_ptx/bond");
```

如果确实需要设备子键，必须先验证非空 ID，再使用有长度限制的格式化函数生成
`ppt_ptx/bond/<stable-id>`；空 ID 时回退到根路径并记录受控错误。

验收：鼠标/接收器完成配对、断电、USB/2.4G/BLE 切换、恢复出厂和多主机覆盖矩阵；
settings 中不得再次产生 `(null)` 键。

### B-08：双传感器能力被单一静态配置覆盖

- 严重度：`high`
- 状态：`confirmed`
- 证据：
  - 固件根据传感器 ID `0x6E/0x53` 选择两张 D086 profile；
  - 相邻能力常量分别包含 40,000 和 30,000 DPI；
  - Launcher 只按产品 PID 使用同一份静态能力配置。

修改方案：

1. 固件新增只读 capability 命令，至少返回：
   `sensor_id/profile_id/dpi_min/dpi_max/dpi_step/lod_values/fps_values/
   polling_values`。
2. Launcher 先读能力再生成控件，静态 JSON 只作为旧固件回退值。
3. 固件对所有写入做范围校验，拒绝非法组合并返回具体错误。
4. BOM 与传感器 ID 建立版本化映射，不用 PID 单独推断传感器。
5. DPI X/Y、13K/20K、125–8000 Hz 和 LOD 必须回读验证。

验收：两种传感器 BOM 分别完成边界值、非法值、升级后保留和恢复默认测试；UI 显示值
与固件回读完全一致。

### B-07：DPI、LOD 与 FPS 规格漂移

- 严重度：`medium`
- 状态：`confirmed`
- 证据：
  - 产品简报为 `1–40000 DPI`，Launcher 为 `50–30000 DPI`，真机能力回读上限为
    `50000`；
  - 产品 LOD 为五档 `0.7/1.0/1.2/1.5/1.7 mm`，Launcher 为
    `0.7/1.0/2.0 mm`；
  - 固件支持 20K 和最高 8K 回报率，但旧协议解析曾隐藏这些能力。

修改方案：产品数据库、固件 capability 和 Launcher 使用同一版本化 schema；发布时
自动比较三方边界。固件拒绝超范围写入，Launcher 所有写入必须立即回读验证。

验收：产品规格、固件能力响应、Launcher 控件和值回读完全一致；最小值、最大值、
步进和非法值测试全部通过。

### B-01：缺少 Security Counter

- 严重度：`medium`
- 状态：`confirmed`

修改方案：

1. 每个可发布版本分配严格递增的 security counter。
2. 使用构建签名流程生成 MCUboot `SECURITY_COUNTER` TLV。
3. Bootloader 在受保护的单调存储中记录已接受值并拒绝更小值。
4. 开发版和量产版使用不同密钥/策略，开发回退不能进入量产设备。

验收：升级到更高 counter 后，使用旧但签名合法的镜像进行降级，必须被拒绝。

### B-02：缺少鼠标/接收器依赖关系

- 严重度：`medium`
- 状态：`confirmed`

修改方案：

1. 为鼠标与接收器定义协议兼容版本，例如 `rf_protocol_major/minor`。
2. 在 Dependency TLV 或同等受签名 manifest 中声明配套最低/最高版本。
3. 升级器在写入前检查版本矩阵；单边升级不兼容时拒绝并说明需要的配套版本。
4. 配对数据格式变更必须提供迁移或回滚路径。

验收：所有允许组合通过连接/配对/8K/休眠测试；所有禁止组合在写入前被拒绝。

### B-04：接收器保留敏感 RF/bond 日志

- 严重度：`medium-low`
- 状态：`conditional-confirmed`

修改方案：

1. 量产 profile 编译移除 access code、完整 bond、信道和 RSSI 详细日志。
2. 必须保留的诊断只输出不可逆短 ID 和枚举错误码。
3. 锁定 SWD/RTT/UART，并把解锁流程纳入受控维修策略。

验收：对发布镜像执行字符串扫描，不得出现 access code/bond 明文格式；量产硬件调试口
访问测试失败。

### B-05：暴露源码路径与断言信息

- 严重度：`low`
- 状态：`confirmed`

修改方案：release 构建关闭无用日志和完整断言文本，使用路径映射去除本机绝对路径；
保留数字 fault ID、模块 ID 和可离线符号化的构建 ID。

验收：发布镜像字符串扫描无本机构建路径；故障仍能通过 build ID + map/ELF 离线定位。

### B-09：USB 无稳定唯一序列号

- 严重度：`medium-low`
- 状态：`confirmed`

修改方案：读取芯片唯一 ID，经产品盐值哈希/截断生成非隐私敏感序列号；应用与
Bootloader 暴露相同值，且不随升级、端口和主机改变。

验收：至少 10 台设备无重复；同一设备正常模式与 recovery 的序列号一致。

### B-10：Boot Mouse 报告兼容性

- 严重度：`medium`
- 状态：`needs-hardware-test`

修改方案：收到 `SET_PROTOCOL(BOOT)` 后切换为标准 Boot Mouse 报告，不发送水平轮或
厂商扩展字段；恢复 Report Protocol 后再使用完整报告。

验收：BIOS、UEFI、KVM、macOS、Windows、Linux 的 Boot/Report Protocol 均完成移动
和按键测试。

### B-12：官方发布链路缺失

- 严重度：`medium`
- 状态：`confirmed`

修改方案：发布 API 同时提供签名镜像、SHA-256、版本、硬件版本、兼容矩阵、security
counter、发布日期、更新说明和恢复包；DVT 与量产渠道分离。

验收：Launcher 能查询当前/最新版本，正确拒绝不兼容包，并支持受控回滚/恢复。

### H-01：待排查 libc/heap SRAM overlay 条件

- 严重度：`high-if-applicable`
- 状态：`hypothesis`

修改方案：取得 `west.yml`、`prj.conf`、DTS/overlay、map 和链接脚本后检查实际 libc、
动态堆与 SRAM 分区；若命中已知冲突，升级相关 SDK/补丁或修正链接区间，并做堆压力、
大包 DFU、8K 输入和无线并发测试。

禁止：在没有构建配置证据时把 H-01 写成此次死机的根因。

## 7. 推荐修复顺序

### P0：先让设备可诊断、可恢复

1. B-11 输入链路有界超时和模块隔离。
2. B-13 独立 watchdog 与 retained 故障记录。
3. B-15 boot-stage GPIO recovery。
4. B-16 独立 MCUboot recovery 与可观测 DFU 状态机。

### P1：修正功能和兼容性

1. B-03 bond settings 根路径。
2. B-08/B-07 动态传感器能力与 Launcher schema。
3. B-02 鼠标/接收器兼容矩阵。
4. B-10 Boot Mouse 报告。

### P2：发布安全与量产质量

1. B-01 防回滚。
2. B-04/B-05 量产日志和路径清理。
3. B-09 稳定设备身份。
4. B-12 发布 API。
5. H-01 构建配置排查。

## 8. 构建与交付流程

1. 获取与 `54LMG6HE`、`54L2DNGC` 对应的完整源码、commit/tag、`west.yml`、
   `prj.conf`、DTS/overlay、分区表、ELF/map 和工具链锁定。
2. 对原始签名文件再次计算 SHA-256，只把它们作为证据和回归基线。
3. 建立开发签名密钥或受控 SWD 流程；不得修改原签名镜像冒充修复版。
4. 先构建诊断版，加入 heartbeat、fault record 和恢复入口。
5. 按 P0/P1/P2 分批修复，每批单独生成变更记录和测试结果。
6. 生成新版本号、安全计数器、依赖 manifest 和签名镜像。
7. 在备用硬件验证 SWD 恢复、USB recovery、断电恢复和错误签名拒绝。
8. 完成鼠标 × 接收器 × Launcher 全矩阵后再进入量产签名。

## 9. 最低验收矩阵

| 维度 | 必测项 |
|---|---|
| 连接 | USB、2.4G、BLE、模式切换、重连 |
| 输入 | 五键、滚轮、横向轮、X/Y、光/磁/混合微动 |
| 性能 | DPI 边界、125/500/1K/2K/4K/8K、13K/20K FPS |
| 电源 | 冷启动、热插拔、睡眠、唤醒、低电、充电 |
| 配对 | 首次配对、覆盖、断电保留、恢复出厂、多主机 |
| 故障注入 | SPI timeout、ADC 恒零、队列满、线程锁死、中断风暴 |
| DFU | 正常、同版重刷、断线、掉电、CRC 错、签名错、回滚 |
| USB 兼容 | Boot/Report Protocol、BIOS、KVM、三大桌面系统 |
| 安全 | anti-rollback、依赖拒绝、调试口、敏感字符串扫描 |

## 10. AI 操作规范

后续 AI 必须遵守：

1. 以问题 ID 为任务主键，不得新建含义重复的编号。
2. 开始修改前读取 `analysis/remediation_manifest.json` 的 `preconditions`。
3. 原始 `.signed.bin` 永远只读；补丁必须作用于源码或新建开发镜像。
4. 没有源码、签名策略或硬件恢复入口时，将任务标记为 `blocked`，不得伪造完成。
5. 每个修复必须输出：
   - 修改文件与 commit；
   - 构建命令和工具链版本；
   - 新镜像 SHA-256；
   - 签名/依赖/security counter 信息；
   - 测试结果和失败清单。
6. `hypothesis` 只能转为 `confirmed` 或 `rejected`，不能直接转为 `fixed`。
7. “命令已发送”不等于“烧录完成”；DFU 完成至少需要 data ACK、CRC/签名校验、
   镜像切换、重新枚举和版本回读。
8. 不得以 USB 仍枚举推断输入链路正常。

AI 推荐执行顺序：

```text
verify_inputs
  -> acquire_source_and_build_lock
  -> establish_recovery_and_backup
  -> build_diagnostic_firmware
  -> fix_P0
  -> fault_injection
  -> fix_P1
  -> compatibility_matrix
  -> fix_P2
  -> sign_release_candidate
  -> recovery_and_upgrade_matrix
  -> release
```

## 11. 当前明确边界

- 已完成：镜像结构审计、内部哈希验证、协议逆向、真机配置回读、复位、输入捕获、
  DFU start/data 尝试。
- 未完成：源码级根因定位、Ed25519 公钥独立验证、完整 flash 备份、修复版量产签名、
  接收器在线联调、全矩阵验收。
- 当前鼠标状态：仍枚举为 `3434:D086`，固件仍为 `1.0.0+5`，普通鼠标输入仍无报告。

## 12. 证据索引

- `analysis/BUG_LEDGER.md`：本轮整理前的静态与运行时缺陷台账
- `analysis/REVERSE_ENGINEERING.md`：二进制调用路径
- `analysis/LIVE_RECOVERY_RESULT_20260723.md`：现场恢复和输入结果
- `analysis/DFU_FLASH_ATTEMPT_20260723.md`：DFU 实机尝试
- `analysis/firmware_report.json`：两份镜像机器可读结构
- `analysis/release_audit.json`：确定性发布审计
- `tools/flash_g6_dfu.py`：本轮 DFU 工具
