# G6 HE 本机源码与构建产物搜索

日期：2026-07-23

## 范围

- `<local-workspace>`
- `<local-data>`
- `<local-desktop>`
- `<local-downloads>`

搜索均为只读；未运行归档中的 Windows 程序，也未搜索或复制无关私钥。

## 搜索键

- 精确固件身份：`54LMG6HE`、`54L2DNGC`、`G6HE_v1.0.0+5`、
  `UltraLink_dongle_rx21`、`3434:D086`；
- 固件内部标识：`ppt_ptx`、`ppt_ptx/bond`、`nrf54lm20`；
- 工程入口：`west.yml`、`prj.conf`、`CMakeLists.txt`、Kconfig、DTS/overlay；
- 构建产物：ELF、map、HEX、signed BIN；
- 归档成员：ZIP、RAR、7z、tar/tgz 内的上述名称和后缀。

## 结果

### 普通文件

- `Work` 扫描 45,875 个文件，没有 G6 HE 固件工程入口、ELF、map 或 HEX；
- `Base`、桌面和 `Downloads` 没有精确身份匹配的源码或构建目录；
- `Downloads/G6 HE固件` 仍只有用户提供的鼠标和接收器签名 BIN；
- 其余 G6 HE 命中均为产品宣讲、规格、渲染图或知识库材料。

### 120 个本地归档的成员名搜索

- 桌面 `G6 HE images.zip` 只有产品图片；
- 两个 2026-07 鼠标产测软件 RAR 只有 `setting.ini`、受 VMProtect 保护的
  Windows EXE 和公共运行库；
- 2026-05 的鼠标日志和 ELF 来自 Airoha AB1623/`keychron_mouse_LM7`
  工程，不是 G6 HE 的 nRF54LM20 平台；
- `LT_Programmer`、`LT_Uart_GUI` 和 LT7589 工程属于 Levetop 显示芯片工具，
  与 G6 HE 无关；
- 没有归档成员命中 `54LMG6HE`、`54L2DNGC`、`ppt_ptx`、
  `UltraLink_dongle_rx21` 或 nRF54LM20 固件工程入口。

### 产测软件身份

- “朱雀 HE”：`362D:D213`；接收器为 `362D:D028` 或 `3434:D083`；
- “Keychron T1 HE”：`3434:D084`；
- 当前 G6 HE 实机：`3434:D086`。

因此这两套产测软件不能被当作 G6 HE 配置器、恢复器或烧录器。

## 补充静态观察

G6 鼠标镜像包含 `hall`、`hall/ax0`、`hall/ax1` settings 子树。对应读取
handler 接收两个 15 字节轴参数块并写入 RAM 配置；当前反汇编没有看到该读取函数中的
永久等待或无界循环。它能证明光磁开关存在持久化校准数据，但尚不足以把本次无响应
归因于 hall 参数。

## 结论

本机可访问资料中仍没有能够复现 `1.0.0+5` / `1.2.1+1` 的源码、ELF/map、
签名流程或官方恢复包。已有确定性二进制补丁会破坏 Ed25519 签名，不能打包成可烧录
固件。下一步仍需固件负责人或供应商提供
[`SOURCE_AND_RECOVERY_REQUEST.md`](SOURCE_AND_RECOVERY_REQUEST.md) 中的资料。

## 公开仓库复核

2026-07-23 又复核了 Keychron 公开代码：

- `Keychron/zgm` 的唯一公开分支为 `main`；
- 当前提交为 `e77d7383750c3b10bf0d52a354886962e7698ec0`；
- 仓库 README 明确说明仍处于 early setup，固件源码、board support、构建和烧录
  指南“仍在准备”；
- 当前仓库只有网站、README、许可和贡献规范，没有 `west.yml`、Zephyr 应用、
  G6 board、传感器驱动或可构建代码；
- 对 `54LMG6HE`、`54L2DNGC`、`UltraLink_dongle_rx21` 的公开精确搜索无结果。

该仓库可作为未来 DIY 方向的上游关注点，但目前不能用于修复或替代本次量产镜像。
