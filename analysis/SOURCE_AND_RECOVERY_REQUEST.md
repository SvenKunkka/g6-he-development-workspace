# 进入固件修复阶段所需资料

请向原固件工程或供应商索取一个完整、可复现的工程包。只有 `.signed.bin` 不足以安全
修复并重新生成可启动镜像。

## 鼠标工程

- `west.yml` 或等价依赖锁定文件；
- `CMakeLists.txt`、`prj.conf` 及所有配置 fragment；
- nRF54LM20A board definition、DTS、overlay、pinctrl；
- PAW3955/PAW3950 传感器驱动和寄存器表；
- 光磁混合微动、MagOptic、模式切换和校准状态机；
- USB HID 描述符及厂商 Feature Report 协议；
- DPI、125–8000 Hz polling、13K/20K FPS、LOD 和按键映射实现；
- 配对、settings/NVS、睡眠唤醒、watchdog、fault handler 和 coredump 配置；
- 当前 `1.0.0+5` 对应 Git commit/tag、ELF、map、HEX 和构建日志。

## UltraLink 接收器工程

- 与鼠标相同类型的 manifest、board/DTS/Kconfig 和构建锁定资料；
- Nordic ESB/私有 2.4G 协议、配对、跳频、包格式和兼容版本定义；
- USB 8K HID 调度、缓冲队列、丢包/重传和无线超时恢复；
- 当前 `1.2.1+1` 对应 Git commit/tag、ELF、map、HEX 和构建日志。

## 启动、签名和恢复

- MCUboot bootloader 源码/配置、分区表和 flash map；
- 当前 Ed25519 keyhash 对应的签名流程；私钥不应通过聊天发送，可由固件负责人在
  受控环境代签；
- 若支持开发 key：bootloader 接受开发 key 的正式流程和回量产 key 的方法；
- SWD 焊盘定义、nRF APPROTECT 状态、可用探针型号及解锁是否会整片擦除；
- 官方 DFU/恢复模式进入方式、传输协议、回滚行为和已验证的救砖镜像；
- 烧录前完整 NVM/settings/bond/校准区备份方法，以及恢复验证步骤。

## 最小验收设备

- 至少 1 只可承担失砖风险的工程样机；
- 该样机唯一身份/序列号或明确 USB 物理端口；
- 对应 UltraLink 接收器；
- 可用 SWD 或官方恢复夹具；
- 鼠标实际传感器 BOM/丝印确认（PAW3950 或 PAW3955）。

资料齐全后，修复流程才能进入：可复现构建 → 基线刷写/回读 → 逐项补丁 →
三轮压力/断电/模式切换/兼容性测试 → 量产签名 → 最终回读校验。
