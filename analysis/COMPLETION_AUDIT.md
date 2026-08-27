# 固件修复目标完成度审计

审计日期：2026-07-23

## 目标与证据

| 要求 | 当前状态 | 权威证据 | 判定 |
|---|---|---|---|
| 重新检查鼠标与接收器固件 | 两份原始镜像身份、布局、内部 SHA-512、向量表和共同 KEYHASH 已验证 | `firmware_report.json`、`release_audit.json` | 已完成 |
| 列出全部 Bug | 已列出 14 项确认缺陷、风险、观察和假设 | `BUG_LEDGER.md` | 部分完成；只有二进制无法证明“全部” |
| 逐个修复 | B-03 已形成确定性补丁规格；其余缺少源码或发布系统 | `binary_patch_spec.json`、`binary_patch_verification.json` | 未完成 |
| 修复后测试 | 18 项分析/策略测试通过；控制页面另有 2 项测试和生产构建通过；没有可启动修复镜像 | `tests/`、`webhid-control/tests/`、测试命令输出 | 固件测试未开始 |
| 至少三轮测试—修复循环 | 已完成三轮审计工具循环；没有完成三轮真机固件循环 | `TEST_CYCLES.md` | 未满足目标 |
| 打包可烧录固件 | 没有受信 Ed25519 签名能力，不能生成 bootloader 接受的镜像 | 两份 TLV、共同 KEYHASH、`burnable_fixed_firmware_ready=false` | 未完成 |
| 真机验证鼠标+接收器 | 当前只连接鼠标且处于输入/Feature Report 无响应现场，接收器已拔除 | `connected_devices_after_three_cycles.json`、`g6_readonly_probe_20260723.json` | 未完成 |

## 当前可证明的补丁

P-01 将鼠标启动路径中指向 `ppt_ptx/bond/(null)` 的 literal pointer 改为镜像中已注册
的 `ppt_ptx/bond` 根路径：

- 签名文件偏移：`0x183DC`
- 原值：`c3fb0420` → `0x2004FBC3`
- 新值：`51fc0420` → `0x2004FC51`
- 目标字符串验证：4/4 检查通过

但修改后原 SHA-512 和 Ed25519 签名立即失效，因此该补丁规格不是可烧录固件。

## 阻塞完成的外部条件

1. 鼠标和 UltraLink 的完整工程源码、板级配置、依赖锁定和当前 ELF/map；
2. MCUboot 接受的开发 key 流程，或由原厂在受控环境完成代签；
3. 唯一目标识别、完整 flash/settings/bond/校准备份和已验证恢复方式；
4. 接回匹配的 UltraLink 接收器，并提供至少一只可承担失砖风险的工程样机。

新增 `<local-workspace>` 根目录已完成 45,875 个文件的二次搜索；
随后又检查 `Base`、桌面、`Downloads` 以及合计 120 个归档的成员名。仍未找到任何
对应工程入口、构建产物、签名流程或恢复包；详见
`analysis/WORKSPACE_SOURCE_SEARCH_20260723.md` 和
`analysis/LOCAL_SOURCE_SEARCH_20260723.md`。

## 结论

当前不能声称目标完成，也不能向用户提供一份伪装成“修复版”的不可启动镜像。交接包
只包含分析、补丁规格和测试工具，明确不含 `.bin/.hex/uf2`，不可用于烧录。
