# G6 HE 二进制逆向定位记录

日期：2026-07-23  
镜像：`G6HE_v1.0.0+5_20260722.signed.bin`  
范围：只读反汇编；未修改或写入真机。

## 正确的运行时地址映射

该镜像是 MCUboot `RAM_LOAD` 镜像：

- Header load address：`0x20000800`
- Header size：`0x800`
- payload/vector table 运行地址：`0x20001000`
- Reset vector：`0x200200BD`，去除 Thumb bit 后为 `0x200200BC`
- Reset handler body offset：`0x1F0BC`

使用 `0x20001000` 作为正文 VMA 后，reset handler 从设置 CONTROL、MSPLIM、
PSPLIM、MSP 开始，指令边界完整；这也纠正了早先按 `0x20000800` 直接映射正文造成的
`0x800` 地址偏差。

## B-03：错误 bond 子树已确认进入启动调用路径

关键证据：

1. 正文 `0x4EBC3` 是字符串 `ppt_ptx/bond/(null)`，运行地址
   `0x2004FBC3`。
2. 正文 `0x17BDC` 保存该字符串指针，签名文件偏移为 `0x183DC`。
3. 初始化函数 `0x20018B48` 在 `0x20018B54` 执行
   `ldr r0, [pc, #132]`，随后在 `0x20018B56` 调用 `0x200402A4`。
4. `0x200402A4` 将 `r1/r2` 清零后尾调用 `0x2001E1AC`，行为与
   `settings_load_subtree(path)` 封装一致。
5. 镜像中另有正确字符串 `ppt_ptx/bond`，运行地址 `0x2004FC51`；settings
   handler 元数据在正文 `0x514A8` 指向这个正确根路径。

因此，启动代码加载的子树与已注册的 handler 根路径不一致。这不再只是字符串疑点。
建议的最小补丁已记录在 `binary_patch_spec.json`；由于签名限制，当前补丁不能直接
刷入。

## B-13：非 fault 型停滞缺少已证实的 watchdog 恢复

异常路径：

`HardFault 0x200200A9`
→ `0x2001FF48`
→ `0x20040B9A`
→ `0x200327A4`
→ `0x20047944`
→ `0x20020DE8`

`0x20020DE8` 会读取 Cortex-M AIRCR 的 PRIGROUP 位，再写入
`0x05FA0004 | PRIGROUP`。其中 `0x05FA` 是 VECTKEY，bit 2 是 SYSRESETREQ；
随后在 `0x20020DFE` 等待硬件复位。因此该循环不是“什么都不做的永久 halt”，而是
复位请求后的等待路径。

接收器的对应路径会先输出 fault 寄存器/线程日志，再由 `0x2000E1FC` 调用
`0x20008298`，执行相同的 AIRCR SYSRESETREQ 并在 `0x200082AE` 等待。

真正的恢复缺口是：镜像包含 watchdog 设备节点、nrfx WDT 驱动和设备初始化函数，
但没有发现 watchdog 设备对象地址被应用代码直接引用。静态证据不能完全排除动态
查找，不过用户观察到“USB 始终枚举、输入永久停止”，更像没有进入 HardFault 的
线程死锁、SPI 永久等待或中断风暴；这些状态不会自动触发 fatal reset。

源码修复应包含：

- 在 fatal reset 前保存 reason、PC、LR 和 fault status；
- 启用独立 watchdog，并由输入/传感器/USB 健康状态共同喂狗；
- 启用 flash coredump 或小型 retained fault record；
- 通过人为触发 HardFault、SPI timeout、主线程锁死和中断风暴验证自动恢复。

## 光磁模式相关路径

镜像存在 `hall`、`hall/ax0`、`hall/ax1` settings 路径：

- `0x2001AA0C` 按轴构造 15 字节 hall 配置并加载 settings；
- `0x2001AA90` 使用 `hall` 根路径进入 settings 保存流程；
- 相邻算法包含阈值、状态和边界判断。

这证明光磁模式会经过独立 hall 配置状态机，但仅凭无符号二进制尚不能把现场死机精确
归因到某个 hall 分支。下一步需要 ELF/map、运行时 fault record，或可烧录开发签名。

早先把 `0xFFC1` 当成 Feature Report 接口是错误的。真机 report descriptor 与
Launcher 前端共同确认它是编号 Output/Input 通道：

- `B3`：63 字节长命令；
- `B4`：63 字节长响应；
- `B5`：20 字节短命令；
- `B6`：20 字节短响应。

死机现场使用正确方向后，全部只读命令均在约 5 ms 内返回。读取到协议版本 `6`、
VID/PID `3434:D086`、版本 `1.0.0+5`。这证明 MCU、USB 和配置线程仍在运行，停止的是
普通鼠标输入路径，而不是整个应用状态机。

协议版本 6 与 feature3 flag 要求使用分离能力命令：

- `0x49`：X/Y DPI；两轴均为 `400/800/1600/3200/5000`，当前档 2；
- `0x4B`：双模式回报率；恢复前当前模式为 level 5（8K）；
- `0x65`：左右 HE 状态；两键 `adc_flag=1`，实时 ADC 均为 `0/0`。

`0x06` 里的第 5 档 `0` 是兼容字段，不是配置损坏。旧 `0x40` 命令返回
`E4 07 40` 是因为本机启用了 v6 X/Y 分离能力。改用正确的 `B3/0x48` 后返回
`E4 00 48`，DPI 表回读一致；使用 `B5/0x4A` 后返回 `E4 00 4A`，当前模式 8K 回读
一致。`B5/0x42` 也成功开启 20K，`0x06` 回读对应位为 1。

## 恢复路径

更新接口 `0x66` 是 system reset。现场验证：

- 设备约 319 ms 后离线；
- 约 844 ms 后重新枚举；
- 固件版本未变；
- 普通鼠标输入仍为 0。

默认 8K 协议的恢复全部是 `B5/0x0F/0xFF`。固件跳转表中 `0x0F` 有独立处理器；
现场返回 `E4 00 0F`，DPI level count 从 6 恢复为 5，回报率从 8K 恢复为 1K。
之后执行系统复位、重新开启 20K 和 8K，三次 12 秒普通鼠标接口抓取仍全部为 0 报告。
因此配置恢复和 MCU 重启均不能解除这次输入链路停滞。

输入处理函数 `0x20016990` 明确检测按键掩码 `0x1B`，并在持续时间大于 2999 ms 时
返回恢复事件 4。`0x1B` 对应左键、右键、前侧键和后侧键。因此“四键长按 3 秒”是该
固件真正实现的物理恢复路径；如果输入扫描本身已经停滞，该组合也可能无法被检测。

Launcher 另有一套 Nordic 8K `0x09` 恢复包，而 `0x2001B13C` 把 `0x09` 指向通用
错误处理器；这台 G6 实际使用 default 8K `0x0F`，不能把两套协议混用。

## 双传感器 profile 与 Launcher 配置漂移

`0x200158C0` 附近的初始化代码读取传感器识别值：

- 返回 `0x6E`：选择 profile `0x2004BB20`，并设置 profile flag `1`；
- 返回 `0x53`：选择 profile `0x2004BBA0`，并设置 profile flag `0`。

两张连续的 `D086` profile 表分别包含 `40000` 与 `30000` 能力常量。这与资料中的
PAW3955/PAW3950 双口径以及 Launcher 固定 30K 上限相互印证。尚不能在没有 BOM/源码
的情况下把 `0x6E/0x53` 强行命名为具体芯片，但可以确认配置器不应只依赖静态 PID：
它需要先读取固件当前选中的 sensor profile，再决定 DPI、LOD 和 FPS 控件范围。
